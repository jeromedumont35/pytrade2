import os
import time
import requests
from pathlib import Path
from CRSIDatabase import CRSIDatabase

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CTestAboveTrend:

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI COURANT (SANS MODIFIER LES WEIGHTS)
    # ======================================================
    def compute_rsi_from_weights(self, weight, new_close, period):
        delta = new_close - weight["last_close"]

        gain = max(delta, 0)
        loss = max(-delta, 0)

        avg_gain = (weight["avg_gain"] * (period - 1) + gain) / period
        avg_loss = (weight["avg_loss"] * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    # ======================================================
    # COMPTE LE NOMBRE DE JOURS AU-DESSUS DU RSI ACTUEL
    # ======================================================
    def count_days_above_rsi(self, DB, symbol, rsi_current):

        if "RSI5" not in DB[symbol]["4h"]:
            print(f"{symbol} : pas d'historique RSI5 4h")
            return 0

        rsi_history = DB[symbol]["4h"]["RSI5"]

        if rsi_history is None or len(rsi_history) == 0:
            return 0

        count = 0

        # parcours du plus récent au plus ancien
        for rsi_value in reversed(rsi_history):
            if rsi_value > rsi_current:
                count += 1
            else:
                break

        # 6 bougies 4h = 1 jour
        days = count / 6.0

        return days

    # ======================================================
    # MAIN
    # ======================================================
    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or len(DB) == 0:
            print(f"{symbol} : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} : dfoneminute vide")
            return False

        if symbol not in DB:
            print(f"{symbol} absent du DB")
            return False

        if "4h" not in DB[symbol]:
            print(f"{symbol} : pas de données 4h")
            return False

        # ===== PRIX COURANT =====
        last_close = dfoneminute["close"].iloc[-1]

        # ===== WEIGHTS =====
        key_weights = "RSI5_WEIGHTS"

        if key_weights not in DB[symbol]["4h"]:
            print(f"{symbol} : pas de weights RSI5 en 4h")
            return False

        weight = DB[symbol]["4h"][key_weights]

        # ===== RSI COURANT 4H =====
        rsi_current = self.compute_rsi_from_weights(
            weight,
            new_close=last_close,
            period=5
        )

        # ===== NOMBRE DE JOURS AU-DESSUS =====
        days_above = self.count_days_above_rsi(DB, symbol, rsi_current)

        # ===== AFFICHAGE =====
        print(
            f"{symbol} | close: {last_close:.4f} | "
            f"RSI4h(5): {rsi_current:.2f} | "
            f"jours au-dessus: {days_above:.2f}"
        )

        return True
