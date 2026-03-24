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
def get_common_spot_symbols():
    r = requests.get("https://api.bitget.com/api/v2/spot/public/symbols", timeout=10)
    r.raise_for_status()
    data = r.json()

    bitget_symbols = {
        f"{s['baseCoin']}USDT"
        for s in data["data"]
        if s.get("quoteCoin") == "USDT"
    }

    r = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=10)
    r.raise_for_status()
    data = r.json()

    binance_symbols = {
        s["symbol"]
        for s in data["symbols"]
        if s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
    }

    return sorted(bitget_symbols.intersection(binance_symbols))


# ==========================================================
# MAP INTERVAL -> FICHIERS
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
# DETECT CHANGES
# ==========================================================
def detect_changed_intervals(old_map, new_map):
    changed = []

    for interval, filename in new_map.items():
        if interval not in old_map or old_map[interval] != filename:
            changed.append(interval)

    return changed


# ==========================================================
# INJECTION WEIGHTS (FACTORISÉ)
# ==========================================================
def inject_weights(DB, weights_all, symbol, interval, period):
    if symbol in weights_all:
        DB[symbol][interval][f"RSI{period}_WEIGHTS"] = {
            "avg_gain": weights_all[symbol]["avg_gain"],
            "avg_loss": weights_all[symbol]["avg_loss"],
            "last_close": weights_all[symbol]["last_close"]
        }


# ==========================================================
# RELOAD INTERVAL
# ==========================================================
def reload_interval(interval, symbols, DB, l_PriceDatabase, l_RSIDatabase, l_rsiperiod):
    print(f"⚡ Reload DB pour interval {interval}")

    price_db_all = l_PriceDatabase.load(resolution=interval)
    rsi_db_all = l_RSIDatabase.load_rsi(resolution=interval, rsi_period=l_rsiperiod)
    weights_all = l_RSIDatabase.load_rsi_weights(resolution=interval, rsi_period=l_rsiperiod)

    for symbol in symbols:

        if symbol not in DB:
            DB[symbol] = {}
        if interval not in DB[symbol]:
            DB[symbol][interval] = {}

        DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
        DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
        DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]

        DB[symbol][interval][f"RSI{l_rsiperiod}"] = \
            rsi_db_all[symbol][interval, f"RSI{l_rsiperiod}"]

        inject_weights(DB, weights_all, symbol, interval, l_rsiperiod)

    print(f"✅ Interval {interval} rechargé.")


# ==========================================================
# CHECK FILES
# ==========================================================
def check_and_update_files():
    global file_map

    new_file_map = map_interval_files(directory)
    changed_intervals = detect_changed_intervals(file_map, new_file_map)

    if changed_intervals:
        print(f"⚠ Intervals modifiés détectés: {changed_intervals}")
        time.sleep(40)

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

symbols = get_common_spot_symbols()
print(f"Symbols utilisés ({len(symbols)}): {symbols}")

available_intervals = ["1d", "1h"]
print(f"Intervals configurés: {available_intervals}")

fetcher = CBitgetDataFetcher.BitgetDataFetcher()
l_PriceDatabase = CPriceDatabase()
l_RSIDatabase = CRSIDatabase()
l_TestOneSymbol = CTestOneSymbol()

l_rsiperiod = 5

# DB INIT
DB = {}
for symbol in symbols:
    DB.setdefault(symbol, {})
    for interval in available_intervals:
        DB[symbol].setdefault(interval, {})

# ==========================================================
# CHARGEMENT INITIAL COMPLET (AVEC WEIGHTS)
# ==========================================================
for interval in available_intervals:

    price_db_all = l_PriceDatabase.load(resolution=interval)
    rsi_db_all = l_RSIDatabase.load_rsi(resolution=interval, rsi_period=l_rsiperiod)
    weights_all = l_RSIDatabase.load_rsi_weights(resolution=interval, rsi_period=l_rsiperiod)

    for symbol in symbols:

        DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
        DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
        DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]

        DB[symbol][interval][f"RSI{l_rsiperiod}"] = \
            rsi_db_all[symbol][interval, f"RSI{l_rsiperiod}"]

        inject_weights(DB, weights_all, symbol, interval, l_rsiperiod)

print(f"✅ DB initialisée avec RSI{l_rsiperiod} + WEIGHTS")

print(DB[symbols[0]]["1h"]["close"].iloc[-1])

# MAP INIT
directory = "."
file_map = map_interval_files(directory)


# ==========================================================
# BOUCLE
# ==========================================================
while True:

    for symbol in symbols:

        check_and_update_files()

        try:
            df = fetcher._fetch_klines3(
                symbol=symbol,
                interval="1m",
                limit=1000
            )

            l_TestOneSymbol.realiser(DB, df, symbol)

        except Exception as e:
            print(f"Erreur fetch pour {symbol}: {e}")
