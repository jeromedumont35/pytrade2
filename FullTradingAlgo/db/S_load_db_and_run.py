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
from CTestOneSymbol import CTestOneSymbol


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
# MAP INTERVAL -> NOM DE FICHIER CSV
# Exemple attendu : 1d_xxxx.csv
# ==========================================================
def map_interval_files(directory: str):
    interval_map = {}

    for f in Path(directory).glob("*.csv"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            interval = parts[0]
            interval_map[interval] = f.name

    return interval_map


# ==========================================================
# DÉTECTER LES INTERVALS MODIFIÉS
# ==========================================================
def detect_changed_intervals(old_map, new_map):
    changed = []

    for interval, filename in new_map.items():
        if interval not in old_map:
            changed.append(interval)
        elif old_map[interval] != filename:
            changed.append(interval)

    return changed


# ==========================================================
# RELOAD D'UN INTERVAL SPÉCIFIQUE
# ==========================================================
def reload_interval(interval, symbols, DB, l_PriceDatabase, l_RSIDatabase, l_rsiperiod):
    print(f"⚡ Reload DB pour interval {interval}")

    price_db_all = l_PriceDatabase.load(resolution=interval)
    rsi_db_all = l_RSIDatabase.load_rsi(resolution=interval, rsi_period=l_rsiperiod)

    for symbol in symbols:
        DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
        DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
        DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]
        DB[symbol][interval][f"RSI{l_rsiperiod}"] = \
            rsi_db_all[symbol][interval, f"RSI{l_rsiperiod}"]

    print(f"✅ Interval {interval} rechargé.")


# ==========================================================
# VÉRIFICATION DES FICHIERS (APPELÉE DANS LA BOUCLE)
# ==========================================================
def check_and_update_files():
    global file_map

    new_file_map = map_interval_files(directory)
    changed_intervals = detect_changed_intervals(file_map, new_file_map)

    if changed_intervals:
        print(f"⚠ Intervals modifiés détectés: {changed_intervals}")
        sleep(2)
        for interval in changed_intervals:
            if interval in available_intervals:
                reload_interval(
                    interval,
                    symbols,
                    DB,
                    l_PriceDatabase,
                    l_RSIDatabase,
                    l_rsiperiod
                )

        file_map = new_file_map


# ==========================================================
# INITIALISATION
# ==========================================================

# 🔹 Récupérer les symbols
symbols = get_usdt_futures_symbols()
symbols = symbols[:100]  # limiter pour test
print(f"Symbols utilisés ({len(symbols)}): {symbols}")

# 🔹 Intervals utilisés
available_intervals = ["1d", "1h"]
print(f"Intervals configurés: {available_intervals}")

# 🔹 Initialisation objets
fetcher = CBitgetDataFetcher.BitgetDataFetcher()
l_PriceDatabase = CPriceDatabase()
l_RSIDatabase = CRSIDatabase()
l_TestOneSymbol = CTestOneSymbol();

l_rsiperiod = 5

# 🔹 Initialiser DB
DB = {}

for symbol in symbols:
    DB.setdefault(symbol, {})
    for interval in available_intervals:
        DB[symbol].setdefault(interval, {})

# 🔹 Charger DB initialement
for interval in available_intervals:
    price_db_all = l_PriceDatabase.load(resolution=interval)
    rsi_db_all = l_RSIDatabase.load_rsi(resolution=interval, rsi_period=l_rsiperiod)

    for symbol in symbols:
        DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
        DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
        DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]
        DB[symbol][interval][f"RSI{l_rsiperiod}"] = \
            rsi_db_all[symbol][interval, f"RSI{l_rsiperiod}"]

print(f"DB initialisée avec RSI{l_rsiperiod}.")

print(DB[symbols[0]]["1h"]["close"].iloc[-1])

# 🔹 Initialiser la map des fichiers (UNE FOIS)
directory = "."
file_map = map_interval_files(directory)


# ==========================================================
# BOUCLE INFINIE
# ==========================================================
while True:

    for symbol in symbols:

        # ✅ Vérification uniquement ici (comme demandé)
        check_and_update_files()

        try:
            df = fetcher._fetch_klines3(
                symbol=symbol,
                interval="1m",
                limit=1000
            )

            l_TestOneSymbol.realiser(DB, df, symbol)

            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Symbol: {symbol}, bougies récupérées: {len(df)}")

        except Exception as e:
            print(f"Erreur fetch pour {symbol}: {e}")

    #time.sleep(60)
