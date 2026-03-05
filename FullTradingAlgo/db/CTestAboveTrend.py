import os
import time
import requests
from pathlib import Path

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CTestAboveTrend:

    def __init__(self):
        pass


    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or len(DB) == 0:
            print(f"{symbol} : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} : dfoneminute vide")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        print(f"{symbol} dernière clôture 1m : {last_close}")

        return True
