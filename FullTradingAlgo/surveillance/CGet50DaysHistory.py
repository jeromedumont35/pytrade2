import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from downloader import CBitgetDataFetcher


class CGet50DaysHistory:
    """
    Récupère les 50 dernières bougies journalières (1D)
    de toutes les paires Futures USDT sur Bitget
    """

    SYMBOLS_URL = "https://api.bitget.com/api/v2/mix/market/contracts"

    def __init__(self):
        self.fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    # ============================
    # Récupération des symbols USDT Futures
    # ============================
    def get_usdt_futures_symbols(self):
        params = {
            "productType": "usdt-futures"
        }

        r = requests.get(self.SYMBOLS_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if "data" not in data:
            raise Exception(f"Erreur API Bitget symbols : {data}")

        symbols = [
            s["symbol"]
            for s in data["data"]
            if s.get("quoteCoin") == "USDT"
        ]

        return sorted(symbols)

    # ============================
    # Téléchargement des 50 dernières bougies 1D
    # ============================
    def fetch(self, nb_days=50, safety_days=80):
        symbols = self.get_usdt_futures_symbols()
        print(f"📊 {len(symbols)} paires USDT Futures détectées")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=safety_days)

        all_dfs = []

        for symbol in symbols:
            try:
                print(f"📥 {symbol} – 1D")

                df = self.fetcher._fetch_klines2(
                    symbol=symbol,
                    interval="1d",
                    start_time=start_time,
                    end_time=end_time
                )

                if df is None or df.empty:
                    continue

                df = df.tail(nb_days)
                all_dfs.append(df)

            except Exception as e:
                print(f"❌ {symbol} erreur : {e}")

        if not all_dfs:
            return pd.DataFrame()

        return pd.concat(all_dfs)
