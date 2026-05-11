import os
import pandas as pd

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.db.CIndicators2 import CIndicators2


class CTestHighDivergence:
    """
    Classe orchestratrice qui teste si un pair respecte la stratégie "Above Trend"
    Utilise les indicateurs de CIndicators pour les calculs
    """

    def __init__(self):
        self.indicators2 = CIndicators2()

    # ======================================================
    # MAIN
    # ======================================================
    def realiser(self, DBOneS, dfoneminute, symbol=None):
        """
        Teste si le pair respecte la stratégie "Above Trend":
        1. RSI5 est le minimum des 2 derniers jours
        2. Close est proche d'une MA daily (10, 20, 50 ou 100)
        3. Close < MA100 (minute)
        4. Le prix a touché la MA100 récemment

        Args:
            DBOneS: Dict avec données d'un symbole (DB[symbol])
            dfoneminute: DataFrame avec données minute
            symbol: Symbole du pair (optionnel, utilisé uniquement pour les logs)

        Returns:
            bool: True si tous les tests passent, False sinon
        """

        symbol_log = symbol if symbol else "UNKNOWN"

        # ======================================================
        # VALIDATIONS BASIQUES
        # ======================================================
        if DBOneS is None or len(DBOneS) == 0:
            print(f"{symbol_log} | FAIL : DBOneS vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol_log} | FAIL : dfoneminute vide")
            return False

        if "4h" not in DBOneS:
            print(f"{symbol_log} | FAIL : pas de données 4h")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        key_weights = "RSI5_WEIGHTS"

        if key_weights not in DBOneS["4h"]:
            print(f"{symbol_log} | FAIL : pas de weights RSI")
            return False

        # ======================================================
        # CALCUL RSI COURANT
        # ======================================================
        rsi_current = self.indicators2.analyse_rsi_min_variation(
            DBOneS=DBOneS,
            dfoneminute=dfoneminute,
            symbol = symbol_log,
            period=5,
            timeframe="4h",
            n_last_values=20,

        )