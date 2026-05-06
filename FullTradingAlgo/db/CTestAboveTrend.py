import os
import pandas as pd

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.db.CIndicators import CIndicators


class CTestAboveTrend:
    """
    Classe orchestratrice qui teste si un pair respecte la stratégie "Above Trend"
    Utilise les indicateurs de CIndicators pour les calculs
    """

    def __init__(self, n_dernieres_minutes_touche_100=60):
        self.n_dernieres_minutes_touche_100 = n_dernieres_minutes_touche_100
        self.indicators = CIndicators()

    # ======================================================
    # MAIN
    # ======================================================
    def realiser(self, DB, dfoneminute, symbol):
        """
        Teste si le pair respecte la stratégie "Above Trend":
        1. RSI5 est le minimum des 2 derniers jours
        2. Close est proche d'une MA daily (10, 20, 50 ou 100)
        3. Close < MA100 (minute)
        4. Le prix a touché la MA100 récemment
        
        Args:
            DB: Base de données avec données par timeframe
            dfoneminute: DataFrame avec données minute
            symbol: Symbole du pair
        
        Returns:
            bool: True si tous les tests passent, False sinon
        """

        # ======================================================
        # VALIDATIONS BASIQUES
        # ======================================================
        if DB is None or len(DB) == 0:
            print(f"{symbol} | FAIL : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} | FAIL : dfoneminute vide")
            return False

        if symbol not in DB:
            print(f"{symbol} | FAIL : symbole absent DB")
            return False

        if "4h" not in DB[symbol]:
            print(f"{symbol} | FAIL : pas de données 4h")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        key_weights = "RSI5_WEIGHTS"

        if key_weights not in DB[symbol]["4h"]:
            print(f"{symbol} | FAIL : pas de weights RSI")
            return False

        weight = DB[symbol]["4h"][key_weights]

        # ======================================================
        # CALCUL RSI COURANT
        # ======================================================
        rsi_current = self.indicators.compute_rsi_from_weights(
            weight,
            new_close=last_close,
            period=5
        )

        # ======================================================
        # ETAPE 1 : RSI MIN
        # ======================================================
        print(f"\n{symbol} | TEST 1 : RSI minimum (2j)")
        if not self.indicators.is_lowest_rsi_last_days(DB, symbol, rsi_current, min_days=2):
            print(f"{symbol} | ❌ FAIL : RSI pas minimum 2j | RSI actuel: {rsi_current:.2f}\n")
            return False
        print(f"{symbol} | ✅ PASS : RSI est minimum | RSI actuel: {rsi_current:.2f}\n")

        # ======================================================
        # ETAPE 2 : PROCHE MA DAILY (1D)
        # ======================================================
        print(f"{symbol} | TEST 2 : Proche MA daily")
        if not self.indicators.is_close_near_daily_ma(DB, symbol, last_close):
            print(f"{symbol} | ❌ FAIL : pas proche MA daily\n")
            return False
        print(f"{symbol} | ✅ PASS : Proche MA daily | close: {last_close:.4f}\n")

        # ======================================================
        # ETAPE 3 : CLOSE < MA100 (1m)
        # ======================================================
        print(f"{symbol} | TEST 3 : Close < MA100 (1min)")
        ma100 = self.indicators.compute_ma100(dfoneminute)
        last_ma100 = ma100.iloc[-1]

        if pd.isna(last_ma100):
            print(f"{symbol} | ❌ FAIL : MA100 NaN\n")
            return False

        if last_close >= last_ma100:
            print(f"{symbol} | ❌ FAIL : close ({last_close:.4f}) >= MA100 ({last_ma100:.4f})\n")
            return False
        
        print(f"{symbol} | ✅ PASS : Close < MA100 | close: {last_close:.4f} < MA100: {last_ma100:.4f}\n")

        # ======================================================
        # ETAPE 4 : TOUCH MA100
        # ======================================================
        print(f"{symbol} | TEST 4 : Touch MA100 (dernières {self.n_dernieres_minutes_touche_100}min)")
        if not self.indicators.has_touched_ma100(dfoneminute, ma100, self.n_dernieres_minutes_touche_100):
            print(f"{symbol} | ❌ FAIL : pas de touch MA100\n")
            return False
        
        print(f"{symbol} | ✅ PASS : MA100 touchée\n")

        # ======================================================
        # SUCCESS
        # ======================================================
        print(
            f"{symbol} | 🎉 SUCCESS - TOUS LES TESTS PASSENT\n"
            f"  • Close: {last_close:.4f}\n"
            f"  • MA100: {last_ma100:.4f}\n"
            f"  • RSI: {rsi_current:.2f}\n"
        )

        return True
