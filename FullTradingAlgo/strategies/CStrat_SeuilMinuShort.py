import pandas as pd
import sys, os
from enum import Enum, auto
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import CTransformToPanda


# ======================================================
# 🧠 États
# ======================================================
class StratState(Enum):
    INIT_ORDER = auto()
    CHECK_ORDER_REACHED = auto()
    POSITION_OPENED = auto()


class CStrat_SeuilMinuShort:

    def __init__(self,
                 interface_trade=None,
                 risk_per_trade_pct: float = 0.1,
                 csv_path: str = "../../surveillance/LauncherListe.csv"):

        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.csv_path = csv_path

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV introuvable : {csv_path}")

        self.df_file = pd.read_csv(csv_path, sep=';')
        self.df_file.columns = self.df_file.columns.str.strip()

        # ==================================================
        # 📌 Lecture CSV UNE SEULE FOIS – par symbole
        # ==================================================
        self.symbol_config = {}

        for _, row in self.df_file.iterrows():
            symbol = row.get("symbol")
            if not isinstance(symbol, str):
                continue

            try:
                seuil_49day = float(row.get("seuil_49day", 0))
            except (TypeError, ValueError):
                seuil_49day = 0.0

            self.symbol_config[symbol] = {
                "seuil_49day": seuil_49day,
                "date0": row.get("date0"),
                "val0": row.get("val0"),
                "date1": row.get("date1"),
                "val1": row.get("val1"),
            }

        self.transformer = CTransformToPanda.CTransformToPanda(
            raw_dir="../raw",
            panda_dir="../panda"
        )

        self.state = {}  # symbol → état

    # ======================================================
    # 🔁 Gestion des états
    # ======================================================
    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {"state": StratState.INIT_ORDER}

    def _set_state(self, symbol, new_state):
        old_state = self.state[symbol]["state"]
        if old_state != new_state:
            print(f"[TRACE] {symbol}: STATE {old_state.name} -> {new_state.name}")
        self.state[symbol]["state"] = new_state

    def _reset_symbol_state(self, symbol):
        self.state[symbol] = {"state": StratState.INIT_ORDER}

    # ======================================================
    # 🕒 Utils temps
    # ======================================================
    @staticmethod
    def parse_date(date_str):
        if date_str is None:
            return None
        date_str = str(date_str).strip()
        if date_str in ("", "0"):
            return None
        return datetime.strptime(date_str, "%d/%m/%Y_%H")

    @staticmethod
    def compute_linear_value(t0, v0, t1, v1, t_now):
        total_sec = (t1 - t0).total_seconds()
        if total_sec <= 0:
            return v0
        alpha = (t_now - t0).total_seconds() / total_sec
        return v0 + alpha * (v1 - v0)

    # ======================================================
    # 📊 Indicators (aucun)
    # ======================================================
    def apply_indicators(self, df, is_btc_file):
        return df.copy()

    # ======================================================
    # 🚀 APPLY (machine à états)
    # ======================================================
    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []
        self._init_symbol_state(symbol)
        state = self.state[symbol]

        if blocked or self.interface_trade is None:
            return actions

        i = df.index.get_loc(timestamp)

        now = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        ).replace(tzinfo=None)

        # ==================================================
        # 🔍 Lecture config symbole
        # ==================================================
        cfg = self.symbol_config.get(symbol)
        if cfg is None:
            return actions

        # ==================================================
        # 🎯 Détermination du threshold_price
        # ==================================================

        # ✅ CAS 1 : seuil_49day fixe pour CE symbole
        if cfg["seuil_49day"] != 0.0:
            threshold_price = cfg["seuil_49day"]

        # 🔁 CAS 2 : interpolation (logique inchangée)
        else:
            t0 = self.parse_date(cfg["date0"])
            t1 = self.parse_date(cfg["date1"])

            if t0 is None or t1 is None:
                return actions

            try:
                v0 = float(cfg["val0"])
                v1 = float(cfg["val1"])
            except (TypeError, ValueError):
                return actions

            threshold_price = self.compute_linear_value(
                t0=t0,
                v0=v0,
                t1=t1,
                v1=v1,
                t_now=now
            )

        # ==================================================
        # 🔎 Vérifier position réelle via Bitget
        # ==================================================
        position_info = self.interface_trade.get_position_info(symbol)

        # ==================================================
        # 🧠 MACHINE À ÉTATS
        # ==================================================

        # 1️⃣ INIT_ORDER
        if state["state"] == StratState.INIT_ORDER:

            self.interface_trade.cancel_all_open_orders(symbol)

            actions.append({
                "action": "OPEN",
                "symbol": symbol,
                "side": "SELL_SHORT",
                "price": threshold_price,
                "sl": [],
                "usdc": self.risk_per_trade_pct,
                "reason": "CSV_SEUIL",
                "entry_index": i
            })

            state["expected_price"] = threshold_price
            state["entry_index"] = i

            self._set_state(symbol, StratState.CHECK_ORDER_REACHED)

        # 2️⃣ CHECK_ORDER_REACHED
        elif state["state"] == StratState.CHECK_ORDER_REACHED:

            if position_info is not None:
                print(f"✅ {symbol} POSITION OUVERTE (Bitget confirmé)")
                state["entry_price"] = position_info["entry_price"]
                state["side"] = position_info["side"]
                self._set_state(symbol, StratState.POSITION_OPENED)

            else:
                self.interface_trade.cancel_all_open_orders(symbol)

                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "SELL_SHORT",
                    "price": threshold_price,
                    "sl": [],
                    "usdc": self.risk_per_trade_pct,
                    "reason": "CSV_SEUIL",
                    "entry_index": i
                })

                state["expected_price"] = threshold_price
                state["entry_index"] = i

        # 3️⃣ POSITION_OPENED
        elif state["state"] == StratState.POSITION_OPENED:
            pass

        return actions

    # ======================================================
    # 📡 Monitoring
    # ======================================================
    def get_symbol_states(self):
        return {sym: st["state"].name for sym, st in self.state.items()}

    def get_main_indicator(self):
        return []


if __name__ == "__main__":
    strat = CStrat_SeuilMinuShort()
    strat.transformer.process_all(strat.apply_indicators)
