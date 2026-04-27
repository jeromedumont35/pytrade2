import os
import time
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CFetcherMultiSymbols import CFetcherMultiSymbols
from FullTradingAlgo.downloader import CBitgetDataFetcher
from CPriceDatabase import CPriceDatabase
from CRSIDatabase import CRSIDatabase
from CTestOneSymbol import CTestOneSymbol
from CLoadDB import CLoadDB


# ==========================================================
# FILTER RSI
# ==========================================================
def filter_symbols_rsi_4h(DB, rsi_period=5, threshold=40):
    filtered = []

    for symbol, data in DB.items():
        try:
            tf_data = data.get("4h", {})
            rsi_series = tf_data.get(f"RSI{rsi_period}", None)

            if rsi_series is None or len(rsi_series) == 0:
                continue

            if rsi_series.iloc[-1] < threshold:
                filtered.append(symbol)

        except Exception as e:
            print(f"RSI filter error {symbol}: {e}")
            continue

    return filtered


# ==========================================================
# INIT
# ==========================================================
available_intervals = ["1d", "4h", "1h"]

fetcher = CBitgetDataFetcher.BitgetDataFetcher()  # FIX: instanciation correcte
l_PriceDatabase = CPriceDatabase()
l_RSIDatabase = CRSIDatabase()
l_TestOneSymbol = CTestOneSymbol()

l_rsiperiod = 5


# ==========================================================
# LOAD DB
# ==========================================================
loader = CLoadDB(
    available_intervals=available_intervals,
    price_db=l_PriceDatabase,
    rsi_db=l_RSIDatabase,
    rsi_period=l_rsiperiod,
    directory="."
)

DB = loader.DB
symbols = loader.symbols

print(f"Symbols utilisés ({len(symbols)})")


# ==========================================================
# LOOP
# ==========================================================
while True:

    try:
        loader.check_and_update_files()

        DB = loader.DB  # 🔥 important : refresh DB à chaque loop

        filtered_symbols = filter_symbols_rsi_4h(
            DB,
            rsi_period=l_rsiperiod,
            threshold=40
        )

        print(f"🎯 {len(filtered_symbols)} symbols avec RSI4h < 40")

        for symbol in filtered_symbols:

            try:
                df = fetcher._fetch_klines3(
                    symbol=symbol,
                    interval="1m",
                    limit=1000
                )

                if df is None or df.empty:
                    continue

                l_TestOneSymbol.realiser(DB, df, symbol)

            except Exception as e:
                print(f"Erreur fetch pour {symbol}: {e}")

    except Exception as e:
        print(f"Erreur boucle principale: {e}")

    time.sleep(1)