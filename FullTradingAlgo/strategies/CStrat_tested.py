import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder


class CStrat_RSI5min30:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")

        # État interne par symbole
        self.state = {}

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "rsi5m_min": None,
                "waiting_rebound": False,
                "first_rebound_price": None,
                "first_rebound_time": None,
                "max_since_rebound": None,
                "waiting_breakout": False,
                "partial_exit_done": False,
            }

    def apply(self, df, symbol, row, timestamp, open_positions):
        actions = []
        self._init_symbol_state(symbol)

        i = df.index.get_loc(timestamp)
        if i < 30:  # besoin d'un minimum pour calculer SL
            return actions

        close = row["close__b_P1"]
        rsi5m = row.get("rsi_5m_14_P2", None)
        rsi4h = row.get("rsi_4h_14_P2", None)

        state = self.state[symbol]
        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        # === GESTION SANS POSITION OUVERTE ===
        if open_pos is None and rsi5m is not None and rsi4h is not None:
            # Étape 1 : on attend un RSI5m < 30
            if rsi5m < 30:
                if state["rsi5m_min"] is None or rsi5m < state["rsi5m_min"]:
                    state["rsi5m_min"] = rsi5m
                return actions

            # Étape 2 : rebond RSI5m détecté
            if state["rsi5m_min"] is not None:
                rebound_target = state["rsi5m_min"] * 1.03

                # Cas A : RSI4h haussier ou neutre
                if not state["waiting_rebound"] and rsi5m >= rebound_target:
                    if rsi4h >= df["rsi_4h_14_P2"].shift(240).iloc[i]:
                        sl_price = df.iloc[i - 30:i]["low"].min()
                        usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                        actions.append({
                            "action": "OPEN",
                            "symbol": symbol,
                            "side": "LONG",
                            "price": close,
                            "sl": sl_price,
                            "usdc": usdc,
                            "position": "LONG",
                            "reason": "CAS_A_SIMPLE_REBOUND"
                        })
                        state.update({"rsi5m_min": None, "waiting_rebound": False,
                                      "first_rebound_price": None, "first_rebound_time": None,
                                      "max_since_rebound": None, "waiting_breakout": False,
                                      "partial_exit_done": False})
                        return actions

                    # Cas B : RSI4h baissier → on attend 30 min après rebond
                    else:
                        state["waiting_rebound"] = True
                        state["first_rebound_price"] = close
                        state["first_rebound_time"] = timestamp
                        state["max_since_rebound"] = close
                        state["waiting_breakout"] = False
                        return actions

                # Cas B suite : suivi de l’attente
                if state["waiting_rebound"]:
                    # mise à jour du max depuis le rebond
                    if close > state["max_since_rebound"]:
                        state["max_since_rebound"] = close

                    elapsed = (timestamp - state["first_rebound_time"]).total_seconds() / 60.0

                    # après 30 minutes → vérifier condition
                    if elapsed >= 30:
                        if close <= state["max_since_rebound"] * 0.99:
                            # on active le mode breakout
                            state["waiting_breakout"] = True
                        else:
                            # reset si condition non remplie
                            state.update({"rsi5m_min": None, "waiting_rebound": False,
                                          "first_rebound_price": None, "first_rebound_time": None,
                                          "max_since_rebound": None, "waiting_breakout": False})
                        return actions

                # Cas B final : cassure haussière après drawdown
                if state.get("waiting_breakout", False) and close > state["max_since_rebound"]:
                    sl_price = df.iloc[i - 30:i]["low"].min()
                    usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                    actions.append({
                        "action": "OPEN",
                        "symbol": symbol,
                        "side": "LONG",
                        "price": close,
                        "sl": sl_price,
                        "usdc": usdc,
                        "position": "LONG",
                        "reason": "CAS_B_BREAKOUT_AFTER_30M"
                    })
                    state.update({"rsi5m_min": None, "waiting_rebound": False,
                                  "first_rebound_price": None, "first_rebound_time": None,
                                  "max_since_rebound": None, "waiting_breakout": False,
                                  "partial_exit_done": False})
                    return actions

        # === GESTION AVEC POSITION OUVERTE ===
        if open_pos is not None and rsi5m is not None:
            sl_price = open_pos.get("sl", None)

            # Stop Loss
            if sl_price is not None and close <= sl_price:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "STOP_LOSS",
                    "position": open_pos
                })
                return actions

            # Take Profit partiel
            if not state["partial_exit_done"] and rsi5m >= 60:
                half_usdc = open_pos.get("usdc", 0) / 2
                actions.append({
                    "action": "PARTIAL_CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": half_usdc,
                    "exit_side": "SELL_LONG",
                    "reason": "TP_PARTIAL",
                    "position": open_pos
                })
                state["partial_exit_done"] = True
                return actions

            # Take Profit total
            if rsi5m >= 70:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "TP_TOTAL",
                    "position": open_pos
                })
                state["partial_exit_done"] = False
                return actions

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        # RSI 4h
        df = CRSICalculator.CRSICalculator(
            df, period=14,
            close_times=[(h, m) for h in range(0, 24, 4) for m in [0]],
            name="rsi_4h_14"
        ).get_df()

        # RSI 5m
        close_times_5m = [(h, m) for h in range(24) for m in range(0, 60, 5)]
        rsi_calc = CRSICalculator.CRSICalculator(df, period=14, close_times=close_times_5m, name="rsi_5m_14")
        df = rsi_calc.get_df()

        df = df.rename(columns={"rsi_4h_14": "rsi_4h_14_P2", "rsi_5m_14": "rsi_5m_14_P2"})
        df = df.rename(columns={"close": "close__b_P1"})

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)


if __name__ == "__main__":
    strat = CStrat_RSI5min30()
    strat.run()
