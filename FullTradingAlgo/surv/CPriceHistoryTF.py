import os
import glob
import time
import sys
import requests
import pandas as pd
from datetime import datetime


class CPriceHistoryTF:
    EXT = ".csv"

    def __init__(self, fetcher, timeframe="1h", limit=1000):
        self.fetcher = fetcher
        self.timeframe = timeframe          # "1h", "1d", "15m", ...
        self.interval = timeframe
        self.limit = limit

        self.prefix = f"data_{self.timeframe}_"
        self.csv_path = None
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

    def _build_filename(self):
        ts = datetime.utcnow().strftime("%Y_%m_%dT%H")
        return f"{self.prefix}{ts}{self.EXT}"

    # =========================
    # Build CSV (CLOSE ONLY)
    # =========================
    def build_csv(self, sleep_between_symbols=0.1):
        self._delete_previous_files()
        self.csv_path = self._build_filename()

        symbols = self.get_usdt_futures_symbols()
        print(f"[{self.timeframe}] {len(symbols)} symbols")

        df_all = None

        for symbol in symbols:
            try:
                print(f"[{self.timeframe}] Fetch {symbol}")

                df = self.fetcher._fetch_klines3(
                    symbol,
                    interval=self.interval,
                    limit=self.limit
                )

                if df is None or df.empty or "close" not in df.columns:
                    continue

                # 🔹 CLOSE UNIQUEMENT
                closes = df["close"].iloc[:-1]        # 999 valeurs
                closes.index = pd.to_datetime(df.index[:-1])
                closes.name = symbol

                if df_all is None:
                    df_all = closes.to_frame()
                else:
                    df_all = df_all.join(closes, how="outer")

                time.sleep(sleep_between_symbols)

            except Exception as e:
                print(f"[{self.timeframe}] Erreur {symbol} : {e}")

        if df_all is None or df_all.empty:
            raise Exception("Aucune donnée collectée")

        df_all.sort_index(inplace=True)

        df_all.to_csv(
            self.csv_path,
            sep=";",
            float_format="%.3e"
        )

        print(f"[{self.timeframe}] CSV créé : {self.csv_path}")

    # =========================
    # Load CSV auto
    # =========================
    def load_csv(self):
        files = sorted(
            glob.glob(f"{self.prefix}*{self.EXT}"),
            reverse=True
        )

        if not files:
            raise FileNotFoundError(
                f"Aucun fichier {self.prefix}*.csv trouvé"
            )

        self.csv_path = files[0]

        self.df = pd.read_csv(
            self.csv_path,
            sep=";",
            index_col=0,
            parse_dates=True
        )

        return self.df

    # =========================
    # Accès données
    # =========================
    def get_symbols(self):
        if self.df is None:
            self.load_csv()
        return list(self.df.columns)

    def get_values(self, symbol):
        if self.df is None:
            self.load_csv()

        if symbol not in self.df.columns:
            raise KeyError(f"Symbol {symbol} absent")

        return self.df[symbol].dropna()


# ==========================================================
# MAIN – exécution directe
# ==========================================================
if __name__ == "__main__":
    from FullTradingAlgo.downloader import CBitgetDataFetcher

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
