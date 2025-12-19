import time
import CheckCSVSeuilMin
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.downloader import CBitgetDataFetcher

my_fetcher = CBitgetDataFetcher.BitgetDataFetcher()
updater = CheckCSVSeuilMin.CheckCSVSeuilMin("LauncherListe.csv", fetcher=my_fetcher, interval="1m")

while True:
    updater.check_and_launch()
    time.sleep(60)   # attendre 1 minute
