import os
import time
import requests
from pathlib import Path

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.db.CTestHighDivergence import CTestHighDivergence
from FullTradingAlgo.db.CTestRSI5Min_MADays import CTestRSI5Min_MADays
from FullTradingAlgo.db.CLauncher3 import CLauncher3


class CTestOneSymbol:
    """
    Classe orchestratrice qui teste un symbole avec différentes stratégies
    """

    def __init__(self):
        self.test_above_trend = CTestHighDivergence()
        self.launcher = CLauncher3()

    def realiser(self, DBOneS, dfoneminute, symbol=None):
        """
        Teste un symbole avec la stratégie "Above Trend"
        
        Args:
            DBOneS: Dict avec données d'un symbole (DB[symbol])
            dfoneminute: DataFrame avec données minute
            symbol: Symbole du pair (optionnel, utilisé uniquement pour les logs)
        
        Returns:
            bool: Résultat du test
        """

        result = self.test_above_trend.realiser(DBOneS, dfoneminute, symbol=symbol)

        # Possibilité de lancer un trade si le test passe
        # if result:
        #    self.launcher.run_launcher(amount=6, symbol=symbol)

        return result
