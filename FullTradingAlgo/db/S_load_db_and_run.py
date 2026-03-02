import os
import time
import requests
from pathlib import Path

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CFetcherMultiSymbols import CFetcherMultiSymbols
from FullTradingAlgo.downloader import CBitgetDataFetcher
from CPriceDatabase import CPriceDatabase
from CRSIDatabase import CRSIDatabase

# ==========================================================
# FONCTION POUR RÉCUPÉRER LES SYMBOLS USDT
# ==========================================================
def get_usdt_futures_symbols():
    params = {"productType": "usdt-futures"}

    r = requests.get(
        "https://api.bitget.com/api/v2/mix/market/contracts",
        params=params,
        timeout=10
    )
    r.raise_for_status()
    data = r.json()

    if "data" not in data:
        raise Exception(f"Erreur API Bitget symbols : {data}")

    return sorted(
        s["symbol"]
        for s in data["data"]
        if s.get("quoteCoin") == "USDT"
    )

# ==========================================================
# FONCTION POUR DÉTECTER LES INTERVALS DISPONIBLES VIA LES CSV
# Exemple de nom de fichier attendu : BTCUSDT_1m.csv, ETHUSDT_15m.csv
# ==========================================================
def detect_available_intervals(directory: str):
    intervals = set()
    for f in Path(directory).glob("*.csv"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            intervals.add(parts[1])
    return sorted(intervals)

# ==========================================================
# INITIALISATION
# ==========================================================

# ?? Récupérer les symbols USDT
symbols = get_usdt_futures_symbols()
symbols = symbols[:2]  # limiter pour test
print(f"Symbols utilisés ({len(symbols)}): {symbols}")

# ?? Détecter les intervalles disponibles dans le répertoire courant
available_intervals = ["1d","1h"]#detect_available_intervals(".")
print(f"Intervals détectés depuis les CSV: {available_intervals}")

# ?? Initialisation du fetcher
fetcher = CBitgetDataFetcher.BitgetDataFetcher()
l_PriceDatabase = CPriceDatabase()
l_RSIDatabase = CRSIDatabase()

l_rsiperiod = 5
DB = {}

for symbol in symbols:
    DB.setdefault(symbol, {})
    for interval in available_intervals:
        DB[symbol].setdefault(interval, {})

# ?? Construire DB par symbol et interval/RSI en appelant load(interval)
for interval in available_intervals:
    price_db_all = l_PriceDatabase.load(resolution=interval)
    rsi_db_all = l_RSIDatabase.load_rsi(resolution=interval, rsi_period=l_rsiperiod)
        
    for symbol in symbols:
         #DB.setdefault(symbol, {})
         #DB[symbol].setdefault(interval, {})
         DB[symbol][interval]["close"]=price_db_all[symbol][interval,"close"]                   
         DB[symbol][interval]["high"]=price_db_all[symbol][interval,"high"]                                                                                                                                                   
         DB[symbol][interval]["low"]=price_db_all[symbol][interval,"low"]
         DB[symbol][interval][f"RSI{l_rsiperiod}"] = rsi_db_all[symbol][interval,"RSI5"]


    

print(f"DB initialisée pour tous les symbols et intervals détectés avec RSI{l_rsiperiod}.")
print(DB["0GUSDT"]["1h"]["close"].iloc[-1])

# ?? Boucle infinie pour récupérer les bougies
while True:
    for symbol in symbols:
        try:
            # ?? On récupère toujours les bougies 1 minute
            df = fetcher._fetch_klines3(symbol=symbol, interval="1m", limit=1000)

            # ?? Afficher un résumé
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Symbol: {symbol}, bougies récupérées: {len(df)}")
        except Exception as e:
            print(f"Erreur fetch pour {symbol}: {e}")

    # ?? Pause avant la prochaine boucle
    time.sleep(60)  # toutes les 1 minute
