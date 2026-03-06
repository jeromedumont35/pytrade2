import os
import time
import requests
from pathlib import Path

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CTestAboveTrend import CTestAboveTrend
from CTestRSI5Min_MADays import CTestRSI5Min_MADays


class CTestOneSymbol:

    def __init__(self):
        self.test_above_trend = CTestAboveTrend()
        self.test_rsi5min_madays = CTestRSI5Min_MADays()


    def realiser(self, DB, dfoneminute, symbol):

        print(f"Analyse du symbole : {symbol}")

        result = self.test_rsi5min_madays.realiser(DB, dfoneminute, symbol)

        return result
