import os
import time
import requests
from pathlib import Path
from CLauncher3 import CLauncher3

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CTestAboveTrend import CTestAboveTrend
from CTestRSI5Min_MADays import CTestRSI5Min_MADays


class CTestOneSymbol:

    def __init__(self):
        self.test_above_trend = CTestAboveTrend()
        self.test_rsi5min_madays = CTestRSI5Min_MADays()
        self.launcher = CLauncher3()


    def realiser(self, DB, dfoneminute, symbol):

        #print(f"Analyse du symbole : {symbol}")

        result = self.test_rsi5min_madays.realiser(DB, dfoneminute, symbol)

        if result > 70:
            self.launcher.run_launcher(amount=6,symbol=symbol)

        return result
