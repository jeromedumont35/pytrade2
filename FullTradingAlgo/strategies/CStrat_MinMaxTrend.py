import pandas as pd
import numpy as np
import sys, os
from enum import Enum, auto

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CMinMaxTrend_V2 as CMinMaxTrend


class StratState(Enum):
    WAIT_REACH_TREND = auto(),
    TRADE_OPEN = auto()

class CStrat_MinMaxTrend:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1,
                 stop_loss_ratio: float = 0.98, max_bars_in_trade: int = 288,
                 break_max_timeout_bars: int = 24):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.max_bars_in_trade = max_bars_in_trade
        self.break_max_timeout_bars = break_max_timeout_bars  # 24 bougies 5m = 2h
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")
        self.state = {}  # symbol → dict état

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "state": StratState.WAIT_REACH_TREND
            }

    def _set_state(self, symbol, new_state):
        """Change d’état avec trace systématique"""
        old_state = self.state[symbol]["state"]
        if old_state != new_state:
            print(f"[TRACE] {symbol}: STATE {old_state.name} -> {new_state.name}")
        self.state[symbol]["state"] = new_state

    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []
        self._init_symbol_state(symbol)
        state = self.state[symbol]

        if blocked:
            return actions

        i = df.index.get_loc(timestamp)

        close = row["close__b_P1"]
        max_line = row.get("Max__c_P1", None)
        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        # =================== MACHINE À ÉTATS ===================

        # 1️⃣ WAIT_REACH_TREND : on attend que le prix soit 3% sous la tendance max
        if state["state"] == StratState.WAIT_REACH_TREND:
            if max_line is not None and not np.isnan(max_line):

                print(max_line)
                #return actions
                self.interface_trade.cancel_all_open_orders(symbol)

                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": max_line,
                    "sl": [],
                    "usdc": self.risk_per_trade_pct,
                    "reason": "PRICE_BELOW_TREND_-3pct",
                    "entry_index": i
                })

                # # Condition d'entrée SHORT : prix sous la tendance de 3%
                # if close > max_line * 0.97:
                #
                #     sl_price = close * 1.03  # SL = +3%
                #     tp_price = close * 0.97  # TP = -3%
                #     usdc = self.risk_per_trade_pct #le risk per trade est en usdc fixe
                #
                #     actions.append({
                #         "action": "OPEN",
                #         "symbol": symbol,
                #         "side": "SHORT",
                #         "price": close,
                #         "sl": sl_price,
                #         "tp": tp_price,
                #         "usdc": usdc,
                #         "reason": "PRICE_BELOW_TREND_-3pct",
                #         "entry_index": i
                #     })
                #
                #     state["entry_index"] = i
                #     state["entry_price"] = close
                    #self._set_state(symbol, StratState.TRADE_OPEN)

        # 2️⃣ TRADE_OPEN : gérer les conditions de sortie (TP / SL)
        elif state["state"] == StratState.TRADE_OPEN and open_pos is not None:
            entry_price = state.get("entry_price", close)

            # Take Profit : le prix baisse encore de 3% après l'entrée
            if close <= entry_price * 0.97:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "BUY_SHORT",
                    "reason": "TP_-3pct",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_REACH_TREND)

            # Stop Loss : le prix monte de 3% après l'entrée
            elif close >= entry_price * 1.03:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "BUY_SHORT",
                    "reason": "SL_+3pct",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_REACH_TREND)

        # 3️⃣ Si pas de trade actif, repasser en attente
        elif state["state"] not in [StratState.WAIT_REACH_TREND, StratState.TRADE_OPEN]:
            self._set_state(symbol, StratState.WAIT_REACH_TREND)

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        # ⚡ Nettoyage de l’index pour éviter les doublons et trier chronologiquement
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        # ==========================================================
        # 🧮 Calcul de la "variabilité" moyenne (|open - close|)
        # ==========================================================
        df["abs_diff"] = (df["open"] - df["close"]).abs()
        mean_abs_diff = df["abs_diff"].mean()

        print(f"📊 Variabilité moyenne (|open - close|) : {mean_abs_diff:.8f}")
        # ==========================================================

        # Calcul d'une trendline max
        calc_max = CMinMaxTrend.CMinMaxTrend(
            df, kind="max", name="Max__c_P1",
            name_init="Init__y_P1",
            p_init=-mean_abs_diff/1.5,  # pente basée sur la variabilité
            CstValideMinutes=10,
            name_slope_change="SlopeChange_+_y_P1",
            mode_day=True
        )
        df = calc_max.get_df()

        #close_times_15m = [(h, m) for h in range(24) for m in range(14, 59, 15)]
        #df = CRSICalculator.CRSICalculator(
        #    df, period=14, close_times=close_times_15m, name="rsi_15m_14_P2"
        #).get_df()

        # 🔹 Renommage colonnes pour la stratégie
        df["close__b_P1"] = df["close"]
        df["high__m_P1"] = df["high"]

        # Nettoyage temporaire de la colonne intermédiaire
        df.drop(columns=["abs_diff"], inplace=True, errors="ignore")

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

    def get_symbol_states(self):
        """
        Retourne un dictionnaire {symbole: état courant}.
        Exemple : {"SHIBUSDC": "WAIT_RSI5M_LOW", "SOLUSDC": "TRADE_OPEN"}
        """
        return {sym: st["state"].name for sym, st in self.state.items()}

    def get_main_indicator(self):
        return ["Max__c_P1"]


if __name__ == "__main__":
    strat = CStrat_MinMaxTrend()
    strat.run()
