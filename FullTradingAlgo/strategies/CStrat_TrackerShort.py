import pandas as pd
from enum import Enum, auto
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda


class StratState(Enum):
    NOT_USED = auto()
    INITIAL_BUY_DONE = auto()
    WAITING_NEW_ENTRY = auto()
    AMOUNT_AUGMENTED = auto()


class CStrat_TrackerShort:
    def __init__(self, trader=None, risk_per_trade_pct: float = 10.0, perf_cible: float = -2.0):
        """
        trader : interface avec méthode get_position_info(symbol)
        """
        self.trader = trader
        self.initial_amount = risk_per_trade_pct
        self.perf_cible = perf_cible
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")
        self.state = {}  # symbol → dict état

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "state": StratState.NOT_USED,
                "rsi_max": None,
            }

    def _set_state(self, symbol, new_state):
        old_state = self.state[symbol]["state"]
        if old_state != new_state:
            print(f"[TRACE] {symbol}: STATE {old_state.name} -> {new_state.name}")
        self.state[symbol]["state"] = new_state

    def _get_perf_info(self, symbol):
        """Récupère montant investi et performance depuis le trader."""
        info = self.trader.get_position_info(symbol)
        if info:
            invested = info.get("invested", 0.0)
            perf = info.get("performance_pct", 0.0)
            return invested, perf
        return 0.0, 0.0

    def get_symbol_states(self):
        """
        Retourne un dictionnaire {symbole: état courant}.
        Exemple : {"SHIBUSDC": "WAIT_RSI5M_LOW", "SOLUSDC": "TRADE_OPEN"}
        """
        return {sym: st["state"].name for sym, st in self.state.items()}

    def _compute_additional_amount(self, invested, perf_actuel):
        """Calcule le montant additionnel pour atteindre perf_cible."""
        perf_target = self.perf_cible
        if perf_actuel >= perf_target:
            return 0.0
        # Exemple : perf_actuel = -5, perf_target = -2 → delta = 3 → ajout ≈ 150%
        add_amount = invested * ((abs(perf_actuel) - abs(perf_target)) / abs(perf_target))
        return round(add_amount, 2)

    # === Core logique ===
    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []
        self._init_symbol_state(symbol)
        state = self.state[symbol]
        rsi = row.get("rsi_5m_14_P2", None)
        close = row["close"]

        if rsi is None or blocked:
            return actions

        # 1️⃣ NOT_USED → entrée initiale
        if state["state"] == StratState.NOT_USED:
            montant = self.initial_amount
            actions.append({
                "action": "OPEN",
                "symbol": symbol,
                "side": "SHORT",
                "price": close,
                "sl": None,
                "usdc": montant,
                "reason": "INITIAL_ENTRY",
                "entry_index": 0
            })
            print(f"[TRACE] {symbol}: Initial short opened ({montant:.2f} USDC @ {close})")
            self._set_state(symbol, StratState.INITIAL_BUY_DONE)
            return actions

        # 2️⃣ INITIAL_BUY_DONE → surveille perf
        elif state["state"] == StratState.INITIAL_BUY_DONE:
            invested, perf = self._get_perf_info(symbol)
            print(f"[TRACE] {symbol}: Perf={perf:.2f}%, Invested={invested:.2f}")

            if perf <= -5.0:
                self._set_state(symbol, StratState.WAITING_NEW_ENTRY)
                state["rsi_max"] = rsi
                print(f"[TRACE] {symbol}: Enter WAITING_NEW_ENTRY, rsi_max={rsi:.2f}")

        # 3️⃣ WAITING_NEW_ENTRY → attend baisse RSI
        elif state["state"] == StratState.WAITING_NEW_ENTRY:
            if state["rsi_max"] is None or rsi > state["rsi_max"]:
                state["rsi_max"] = rsi

            if rsi <= state["rsi_max"] - 3:
                invested, perf = self._get_perf_info(symbol)
                add_amount = self._compute_additional_amount(invested, perf)

                if add_amount > 0:
                    actions.append({
                        "action": "OPEN",
                        "symbol": symbol,
                        "side": "SHORT",
                        "price": close,
                        "sl": None,
                        "usdc": add_amount,
                        "reason": f"RSI_DROP_FROM_MAX ({state['rsi_max']:.2f}->{rsi:.2f})",
                        "entry_index": 0
                    })
                    print(f"[TRACE] {symbol}: Add short {add_amount:.2f} USDC to target {self.perf_cible}%")
                    self._set_state(symbol, StratState.AMOUNT_AUGMENTED)

        # 4️⃣ AMOUNT_AUGMENTED → surveille perf
        elif state["state"] == StratState.AMOUNT_AUGMENTED:
            invested, perf = self._get_perf_info(symbol)
            print(f"[TRACE] {symbol}: (AMOUNT_AUGMENTED) Perf={perf:.2f}%, Invested={invested:.2f}")

            if perf >= 1.0:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "sl": None,
                    "usdc": invested,
                    "reason": "PROFIT_TARGET_REACHED",
                    "entry_index": 0
                })
                print(f"[TRACE] {symbol}: Close trade, profit >= +1%")
                self._set_state(symbol, StratState.NOT_USED)

            elif perf <= -5.0:
                self._set_state(symbol, StratState.WAITING_NEW_ENTRY)
                state["rsi_max"] = rsi
                print(f"[TRACE] {symbol}: Perf={perf:.2f}%, retour WAITING_NEW_ENTRY")

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()
        df = df[~df.index.duplicated(keep='last')].sort_index()

        # RSI 5m
        close_times_5m = [(h, m) for h in range(24) for m in range(4, 59, 5)]
        df = CRSICalculator.CRSICalculator(
            df, period=14, close_times=close_times_5m, name="rsi_5m_14_P2"
        ).get_df()

        return df

    def get_main_indicator(self):
        return ["rsi_5m_14_P2"]
