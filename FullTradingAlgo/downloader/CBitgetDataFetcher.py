import requests
import time
import pandas as pd
from datetime import datetime, timedelta, timezone

class BitgetDataFetcher:
    BASE_URL = "https://api.bitget.com/api/v2/mix/market/candles"

    # Intervalles valides selon Bitget API v2
    INTERVAL_MAP = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1H",
        "4h": "4H",
        "6h": "6H",
        "12h": "12H",
        "1d": "1D",
        "1w": "1W",
        "1M": "1M"
    }

    def __init__(self):
        pass

    def _prepare_dataframe(self, candles):
        df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume","x"])
        df["time"] = pd.to_datetime(pd.to_numeric(df["time"]), unit="ms", utc=True)
        df.set_index("time", inplace=True)
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df["moy_l_h_e_c"] = (df["open"] + df["close"] + df["high"] + df["low"]) / 4
        return df[["open", "high", "low", "close", "volume", "moy_l_h_e_c"]]

    def _fetch_klines(self, symbol, interval, start_time, end_time, max_retries=3):
        if interval not in self.INTERVAL_MAP:
            raise ValueError(f"Interval '{interval}' non supporté. Choisis parmi : {list(self.INTERVAL_MAP.keys())}")

        granularity = self.INTERVAL_MAP[interval]
        url = self.BASE_URL
        limit = 720
        all_candles = []

        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        while True:
            params = {
                "symbol": symbol,
                "granularity": granularity,
                #"startTime": start_ts,
                #"endTime": end_ts,
                "limit": limit,
                "productType": "usdt-futures"
            }

            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, timeout=(3, 5))
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception as e:
                    print(f"[{symbol}] Erreur réseau : {e} (tentative {attempt+1}/{max_retries})")
                    time.sleep(2)
            else:
                print(f"[{symbol}] Échec après {max_retries} tentatives → arrêt du fetch.")
                return None

            if not isinstance(data, dict) or "data" not in data:
                raise Exception(f"Erreur API Bitget : {data}")

            candles = data["data"]
            if not candles:
                break

            candles = sorted(candles, key=lambda x: x[0])
            all_candles.extend(candles)

            last_ts = int(candles[-1][0])
            start_ts = last_ts + 1
            if start_ts >= end_ts:
                break

        if not all_candles:
            return pd.DataFrame()

        df = self._prepare_dataframe(all_candles)
        df["symbol"] = symbol
        return df

    def get_historical_klines(self, symbols, interval="1m", days=1):
        end_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
        start_time = end_time - timedelta(days=days)

        all_dfs = []
        for sym in symbols:
            print(f"Téléchargement {sym} ({interval}) ...")
            df = self._fetch_klines(sym, interval, start_time, end_time)
            if df is not None and not df.empty:
                all_dfs.append(df)

        return pd.concat(all_dfs) if all_dfs else pd.DataFrame(columns=["open","high","low","close","volume","moy_l_h_e_c","symbol"])

    def get_last_complete_kline(self, symbols, interval="1m"):
        end_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
        start_time = end_time - timedelta(minutes=3)

        all_dfs = []
        for sym in symbols:
            df = self._fetch_klines(sym, interval, start_time, end_time)
            if df is not None and not df.empty:
                all_dfs.append(df.iloc[[-1]])

        return pd.concat(all_dfs) if all_dfs else pd.DataFrame(columns=["open","high","low","close","volume","moy_l_h_e_c","symbol"])
