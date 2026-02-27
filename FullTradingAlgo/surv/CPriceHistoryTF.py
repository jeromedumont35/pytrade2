import os
import glob
import time
import sys
import requests
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from FullTradingAlgo.downloader import CBitgetDataFetcher


class CPriceHistoryTF:
    EXT = ".csv"

    def __init__(self, fetcher, timeframe="1h", limit=1000):
        self.fetcher = fetcher
        self.timeframe = timeframe
        self.interval = timeframe
        self.limit = limit

        self.prefix = f"data_{self.timeframe}_"
        self.df = None

    # =========================
    # Symbols USDT Futures
    # =========================
    def get_usdt_futures_symbols(self):
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

    # =========================
    # Gestion fichiers
    # =========================
    def _delete_previous_files(self):
        for f in glob.glob(f"{self.prefix}*{self.EXT}"):
            os.remove(f)

    def _build_filename(self, price_type):
        ts = datetime.utcnow().strftime("%Y_%m_%dT%H%M")
        return f"{self.prefix}{price_type}_{ts}{self.EXT}"

    # =========================
    # Build CSV (HIGH / LOW / CLOSE)
    # =========================
    def build_csv(self, sleep_between_symbols=0.1):
        self._delete_previous_files()

        symbols = self.get_usdt_futures_symbols()
        print(f"[{self.timeframe}] {len(symbols)} symbols")

        datasets = {
            "high": None,
            "low": None,
            "close": None
        }

        symbols = ["BTCUSDT"]

        for symbol in symbols[:5]:  # 🔹 LIMIT 5 POUR TEST
            try:
                print(f"[{self.timeframe}] Fetch {symbol}")

                df = self.fetcher._fetch_klines3(
                    symbol,
                    interval=self.interval,
                    limit=self.limit
                )

                if df is None or df.empty:
                    continue

                # Exclure la bougie en cours
                df = df.iloc[:-1]
                df.index = pd.to_datetime(df.index)

                for price_type in datasets.keys():
                    if price_type not in df.columns:
                        continue

                    series = df[price_type].copy()
                    series.name = symbol

                    if datasets[price_type] is None:
                        datasets[price_type] = series.to_frame()
                    else:
                        datasets[price_type] = datasets[price_type].join(
                            series, how="outer"
                        )

                time.sleep(sleep_between_symbols)

            except Exception as e:
                print(f"[{self.timeframe}] Erreur {symbol} : {e}")

        for price_type, df_all in datasets.items():
            if df_all is None or df_all.empty:
                print(f"[{self.timeframe}] Aucun {price_type}")
                continue

            df_all.sort_index(inplace=True)

            path = self._build_filename(price_type)
            df_all.to_csv(
                path,
                sep=";",
                float_format="%.3e"
            )

            print(f"[{self.timeframe}] CSV {price_type} créé : {path}")


# ==========================================================
# MAIN – exécution directe
# ==========================================================
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage : python CPriceHistoryTF.py <timeframe>")
        print("Exemples : 1h | 1d | 15m")
        sys.exit(1)

    timeframe = sys.argv[1]

    fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    manager = CPriceHistoryTF(
        fetcher=fetcher,
        timeframe=timeframe,
        limit=1000
    )

    manager.build_csv()
