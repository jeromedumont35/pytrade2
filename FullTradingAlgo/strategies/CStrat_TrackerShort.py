import pandas as pd
from enum import Enum, auto
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda


class StratState(Enum):
    WAITING_ENTRY = auto()
    INITIAL_BUY_DONE = auto()
    WAITING_NEW_ENTRY = auto()
    AMOUNT_AUGMENTED = auto()


class CStrat_TrackerShort:
    def __init__(self, trader=None, risk_per_trade_pct: float = 10.0, perf_cible: float = -1.5):
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
            # 🔁 État initial = WAITING_ENTRY
            self.state[symbol] = {
                "state": StratState.WAITING_ENTRY,
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
        """Retourne un dictionnaire {symbole: état courant}"""
        return {sym: st["state"].name for sym, st in self.state.items()}

    def _compute_additional_amount(self, invested, perf_actuel):
        """Calcule le montant additionnel pour atteindre perf_cible."""
        perf_target = self.perf_cible
        if perf_actuel >= perf_target:
            return 0.0
        add_amount = invested * ((abs(perf_actuel) - abs(perf_target)) / abs(perf_target))
        return round(add_amount, 2)

    # === Core logique ===
    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []
        self._init_symbol_state(symbol)
        state = self.state[symbol]
        close = row["close"]
        rsi_15m = row.get("rsi_15m_9_P2", None)
        rsi_3m = row.get("rsi_3m_9_P2", None)

        if rsi_15m is None or rsi_3m is None or blocked:
            return actions

        # 1️⃣ WAITING_ENTRY → vérifier conditions d’entrée SHORT
        if state["state"] == StratState.WAITING_ENTRY:
            if rsi_3m > 80 and rsi_15m > 70:
                montant = self.initial_amount
                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "sl": None,
                    "usdc": montant,
                    "reason": "INITIAL_ENTRY_RSI_CONDITION",
                    "entry_index": 0
                })
                print(f"[TRACE] {symbol}: RSI3m={rsi_3m:.2f} RSI15m={rsi_15m:.2f} → SHORT {montant:.2f} USDC @ {close}")
                self._set_state(symbol, StratState.INITIAL_BUY_DONE)
                return actions

        # 2️⃣ INITIAL_BUY_DONE → surveille performance
        elif state["state"] == StratState.INITIAL_BUY_DONE:
            invested, perf = self._get_perf_info(symbol)
            print(f"[TRACE] {symbol}: Perf={perf:.2f}%, Invested={invested:.2f}")
            if perf <= -5.0:
                self._set_state(symbol, StratState.WAITING_NEW_ENTRY)
                state["rsi_max"] = rsi_15m
                state["price_max_after_wait"] = close
                print(f"[TRACE] {symbol}: Enter WAITING_NEW_ENTRY, rsi_max={rsi_15m:.2f}, price_max={close:.2f}")

        # 🔁 Le reste de la logique est inchangé
        elif state["state"] == StratState.WAITING_NEW_ENTRY:
            if state.get("rsi_max") is None or rsi_15m > state["rsi_max"]:
                state["rsi_max"] = rsi_15m
            if state.get("price_max_after_wait") is None or close > state["price_max_after_wait"]:
                state["price_max_after_wait"] = close

            if rsi_15m <= state["rsi_max"] - 3:
                self._set_state(symbol, StratState.AMOUNT_AUGMENTED)
                print(f"[TRACE] {symbol}: RSI drop detected ({state['rsi_max']:.2f} → {rsi_15m:.2f}), enter AMOUNT_AUGMENTED")

        elif state["state"] == StratState.AMOUNT_AUGMENTED:
            invested, perf = self._get_perf_info(symbol)
            print(f"[TRACE] {symbol}: AMOUNT_AUGMENTED Perf={perf:.2f}%")
            if perf >= 1.0:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "usdc": invested,
                    "reason": "PROFIT_TARGET_REACHED",
                    "entry_index": 0
                })
                print(f"[TRACE] {symbol}: Close trade, profit >= +1%")
                self._set_state(symbol, StratState.WAITING_ENTRY)

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()
        df = df[~df.index.duplicated(keep='last')].sort_index()

        # RSI 15m
        close_times_15m = [(h, m) for h in range(24) for m in range(14, 60, 15)]
        df = CRSICalculator.CRSICalculator(
            df, period=9, close_times=close_times_15m, name="rsi_15m_9_P2"
        ).get_df()

        # RSI 3m
        close_times_3m = [(h, m) for h in range(24) for m in range(2, 60, 3)]
        df = CRSICalculator.CRSICalculator(
            df, period=9, close_times=close_times_3m, name="rsi_3m_9_P2"
        ).get_df()

        return df

    def get_main_indicator(self):
        return ["rsi_3m_9_P2", "rsi_15m_9_P2"]
