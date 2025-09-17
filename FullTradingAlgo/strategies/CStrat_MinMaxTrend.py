import pandas as pd
import numpy as np
import sys, os
from enum import Enum, auto

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CMinMaxTrend


class StratState(Enum):
    WAIT_RSI5M_LOW = auto()
    WAIT_REBOUND_UP = auto()
    WAIT_REBOUND_DOWN = auto()
    WAIT_AFTER_MAX = auto()
    WAIT_BREAK_MAX = auto()
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

    def get_main_indicator(self):
        return 0  # ["rsi_5m_14_P2", "rsi_4h_14_P2"]

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "state": StratState.WAIT_RSI5M_LOW,
                "rsi5m_min": None,
                "rebound_max_price": None,
                "wait_start_index": None,
                "entry_index": None,
                "break_max_start_index": None,
                "entry_price": None
            }

    def _reset_symbol_state(self, symbol, new_state=StratState.WAIT_RSI5M_LOW):
        """Réinitialise complètement l'état du symbole et définit l'état initial."""
        old_state = self.state[symbol]["state"] if symbol in self.state else None
        print(f"[TRACE] {symbol}: RESET state {old_state} -> {new_state}")
        self.state[symbol] = {
            "state": new_state,
            "rsi5m_min": None,
            "rebound_max_price": None,
            "wait_start_index": None,
            "entry_index": None,
            "break_max_start_index": None,
            "entry_price": None
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

        i = df.index.get_loc(timestamp)
        if i < 240:
            return actions

        close = row["close__b_P1"]
        high = row["high"]
        max_line = row.get("Max__c_P1", None)
        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        # =================== MACHINE À ÉTATS ===================

        # Valeur précédente de max_line pour comparer
        prev_max_line = df["Max__c_P1"].shift(1).iloc[i]

        # 1️⃣ WAIT_BREAK_MAX : attendre le dépassement de la trendline max
        if state["state"] == StratState.WAIT_BREAK_MAX:
            if prev_max_line is not None and not np.isnan(prev_max_line):

                if high > prev_max_line + 0.1:  # cassure par le haut
                    slope_changes = df.loc[:timestamp, "SlopeChange_+_y_P1"].dropna().index
                    if len(slope_changes) >= 2:
                        last_slope_change_idx = slope_changes[-2]  # l’avant-dernier
                    elif len(slope_changes) == 1:
                        last_slope_change_idx = slope_changes[-1]  # il n’y a qu’un seul slope change connu
                    else:
                        last_slope_change_idx = None

                    if last_slope_change_idx is not None:
                        minutes_since_last_change = (timestamp - last_slope_change_idx).total_seconds() / 60.0
                        if minutes_since_last_change < 7200:
                            print(f"[TRACE] {symbol}: cassure détectée mais slope change trop récent "
                                  f"({minutes_since_last_change:.0f} min < 240 min)")
                            return actions

                    if blocked:
                        self._set_state(symbol, StratState.WAIT_BREAK_MAX)
                        return actions

                    sl_price = close * 0.98  # SL = -2%
                    usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct

                    actions.append({
                        "action": "OPEN",
                        "symbol": symbol,
                        "side": "LONG",
                        "price": close,
                        "sl": sl_price,
                        "usdc": usdc,
                        "reason": "BREAK_MAX_LINE",
                        "entry_index": i
                    })

                    state["entry_index"] = i
                    state["entry_price"] = close
                    self._set_state(symbol, StratState.TRADE_OPEN)


        # 2️⃣ TRADE_OPEN : gérer les conditions de sortie
        elif state["state"] == StratState.TRADE_OPEN and open_pos is not None:
            entry_price = state.get("entry_price", close)

            # Condition de perte -3%
            if close <= entry_price * 0.97:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "PRICE_DROP_3PCT",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_BREAK_MAX)

            # Condition de gain +3%
            elif close >= entry_price * 1.03:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "PRICE_UP_3PCT",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_BREAK_MAX)

        # 3️⃣ Si pas de trade et pas en attente → retour état initial
        elif state["state"] not in [StratState.WAIT_BREAK_MAX, StratState.TRADE_OPEN]:
            self._set_state(symbol, StratState.WAIT_BREAK_MAX)

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        # ⚡ Nettoyage de l’index pour éviter les doublons et trier chronologiquement
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        # Calcul d'une trendline max
        calc_max = CMinMaxTrend.CMinMaxTrend(
            df, kind="max", name="Max__c_P1",
            name_init="Init__y_P1", p_init=-0.04,
            CstValideMinutes=30, name_slope_change="SlopeChange_+_y_P1"
        )
        df = calc_max.get_df()

        # # RSI 4H calculé mais plus utilisé pour la sortie
        # df = CRSICalculator.CRSICalculator(
        #     df, period=14,
        #     close_times=[(h, m) for h in range(3, 23, 4) for m in [59]],
        #     name="rsi_4h_14_P2"
        # ).get_df()

        # 🔹 Renommage colonnes pour la stratégie
        df["close__b_P1"] = df["close"]
        df["high__m_P1"] = df["high"]

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

    def get_symbol_states(self):
        """
        Retourne un dictionnaire {symbole: état courant}.
        Exemple : {"SHIBUSDC": "WAIT_RSI5M_LOW", "SOLUSDC": "TRADE_OPEN"}
        """
        return {sym: st["state"].name for sym, st in self.state.items()}


if __name__ == "__main__":
    strat = CStrat_MinMaxTrend()
    strat.run()
