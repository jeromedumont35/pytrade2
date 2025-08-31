import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder


class CStrat_RSI5min30:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98, max_bars_in_trade: int = 288):
        """
        :param interface_trade: interface de trading pour récupérer le solde USDC
        :param risk_per_trade_pct: % du capital à risquer par trade
        :param stop_loss_ratio: ratio du stop loss (non utilisé directement, on prend le plus bas des 30 dernières bougies)
        :param max_bars_in_trade: nombre max de bougies 1min avant de forcer la fermeture (fail-safe)
        """
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.max_bars_in_trade = max_bars_in_trade
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")

        # État interne par symbole
        self.state = {}

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "rsi5m_min": None,
                "waiting_rebound": False,
                "first_rebound_price": None,
                "partial_exit_done": False,
                "waiting_rebound_start_index": None,
                "rebound_max_price": None,
            }

    def _reset_symbol_state(self, symbol):
        """Réinitialise complètement l'état du symbole."""
        self.state[symbol] = {
            "rsi5m_min": None,
            "waiting_rebound": False,
            "first_rebound_price": None,
            "partial_exit_done": False,
            "waiting_rebound_start_index": None,
            "rebound_max_price": None,
        }

    def apply(self, df, symbol, row, timestamp, open_positions):
        actions = []
        self._init_symbol_state(symbol)

        i = df.index.get_loc(timestamp)
        if i < 240:  # besoin d'un minimum pour comparer avec 4h avant
            return actions

        close = row["close__b_P1"]
        rsi5m = row.get("rsi_5m_14_P2", None)
        rsi4h = row.get("rsi_4h_14_P2", None)

        state = self.state[symbol]
        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        # === GESTION SANS POSITION OUVERTE ===
        if open_pos is None and rsi5m is not None and rsi4h is not None:

            # === Phase RSI < 30 ===
            if rsi5m < 30:
                # On garde toujours la trace du plus bas RSI
                if state["rsi5m_min"] is None or rsi5m < state["rsi5m_min"]:
                    state["rsi5m_min"] = rsi5m

                # On ne reset l'attente que si on était déjà en rebond et qu'on replonge
                if state["waiting_rebound"]:
                    state["waiting_rebound"] = False
                    state["waiting_rebound_start_index"] = None
                    state["rebound_max_price"] = None

                return actions

            # === Phase RSI >= 30 ===
            if state["rsi5m_min"] is not None:
                rebound_target = state["rsi5m_min"] * 1.03

                # === Cas A : RSI4h haussier ou neutre → entrée directe ===
                if not state["waiting_rebound"]:
                    if rsi4h >= df["rsi_4h_14_P2"].shift(240).iloc[i] * 1.05 and rsi5m > rebound_target:
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
                            "reason": "CAS_A_SIMPLE_REBOUND",
                            "entry_index": i
                        })

                        actions.append({
                            "action": "M1",
                            "symbol": symbol,
                            "side": "LONG",
                            "price": close,
                            "position": "LONG",
                            "reason": "CAS_A_SIMPLE_REBOUND",
                            "entry_index": i
                        })

                        self._reset_symbol_state(symbol)
                        return actions

                    # === Cas B : RSI4h baissier → attente de 30 min pour confirmer ===
                    elif rsi4h < df["rsi_4h_14_P2"].shift(240).iloc[i] * 0.95 and rsi5m > rebound_target :
                        # ✅ On exige RSI 4h < 25 pour lancer l’attente
                        if rsi4h < 30:
                            state["waiting_rebound"] = True
                            state["waiting_rebound_start_index"] = i
                            state["rebound_max_price"] = close
                            actions.append({
                                "action": "M2",
                                "symbol": symbol,
                                "side": "LONG",
                                "price": close,
                                "position": "LONG",
                                "reason": "CAS_A_SIMPLE_REBOUND",
                                "entry_index": i
                            })
                        return actions

                # === Cas B suite : on attend 30 minutes puis on casse le max ===
                if state["waiting_rebound"]:
                    # ✅ Reset si RSI4h repasse au-dessus de 50
                    if rsi4h > 50:
                        self._reset_symbol_state(symbol)
                        return actions

                    # Mise à jour du max pendant les 30 minutes
                    if i - state["waiting_rebound_start_index"] <= 30:
                        state["rebound_max_price"] = max(state["rebound_max_price"], close)
                        return actions

                    # Après 30 minutes → si le close casse le max enregistré
                    if close > state["rebound_max_price"]:
                        sl_price = df.iloc[i - 15:i]["low"].min()
                        usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                        actions.append({
                            "action": "OPEN",
                            "symbol": symbol,
                            "side": "LONG",
                            "price": close,
                            "sl": sl_price,
                            "usdc": usdc,
                            "position": "LONG",
                            "reason": "CAS_B_DOUBLE_CONFIRMATION",
                            "entry_index": i
                        })
                        self._reset_symbol_state(symbol)
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
                self._reset_symbol_state(symbol)
                return actions

            # # Take Profit partiel
            # if not state["partial_exit_done"] and rsi5m >= 60:
            #     half_usdc = open_pos.get("usdc", 0) / 2
            #     actions.append({
            #         "action": "PARTIAL_CLOSE",
            #         "symbol": symbol,
            #         "side": "LONG",
            #         "price": close,
            #         "exit_price": close,
            #         "usdc": half_usdc,
            #         "exit_side": "SELL_LONG",
            #         "reason": "TP_PARTIAL",
            #         "position": open_pos
            #     })
            #     state["partial_exit_done"] = True
            #     return actions

            # Take Profit total
            if rsi5m >= 60:
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
                self._reset_symbol_state(symbol)
                return actions

            # Fail-safe : fermeture après X bougies 1min
            if "entry_index" in open_pos and (i - open_pos["entry_index"]) >= self.max_bars_in_trade:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "TIME_BASED_EXIT",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol)
                return actions

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        # RSI 4h (calculé depuis bougies 1min)
        df = CRSICalculator.CRSICalculator(
            df, period=14,
            close_times=[(h, m) for h in range(0, 24, 4) for m in [0]],
            name="rsi_4h_14"
        ).get_df()

        # RSI 5m (calculé depuis bougies 1min)
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
