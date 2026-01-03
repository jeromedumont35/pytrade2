import pandas as pd
import numpy as np
import sys, os
from enum import Enum, auto

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CMACalculator
import CTransformToPanda


class StratState(Enum):
    WAIT_REACH_TREND = auto(),
    TRADE_OPEN = auto()

class CStrat_TestIndicators:
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
           print("ici")
        elif state["state"] == StratState.TRADE_OPEN and open_pos is not None:
            print("ici2")

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        # ⚡ Nettoyage de l’index pour éviter les doublons et trier chronologiquement
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        close_times_15m = [(h, m) for h in range(24) for m in range(14, 59, 15)]
        #df = CMACalculator.CMACalculator(
        #    df,
        #    period=20,
        #    close_times=[(h, m) for h in range(3, 23, 4) for m in [59]],
        #    name="ma_4h_20__y_P1"
        #).get_df()

        df = CMACalculator.CMACalculator(
            df,
            period=20,
            close_times=[(h, m) for h in range(0, 24, 1) for m in range(0, 60, 1)],
            name="ma_m1_20__y_P1"
        ).get_df()

        # 🔹 Renommage colonnes pour la stratégie
        df["close__b_P1"] = df["close"]
        df["close__r_P1"] = df["high"]

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
    strat = CStrat_TestIndicators()
    strat.run()
