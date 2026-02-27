import pandas as pd
import time


class CFetcherMultiSymbols:
    def __init__(self, fetcher, interval="15m", limit=500):
        """
        fetcher : objet possédant la méthode _fetch_klines3(symbol, interval, limit)
        interval : timeframe Binance (ex: '1m', '5m', '15m', '1h')
        limit : nombre de bougies à récupérer
        """
        self.fetcher = fetcher
        self.interval = interval
        self.limit = limit

    def fetch(self, symbols, sleep_between_symbols=0.1):
        """
        symbols : liste de symboles (ex: ["BTCUSDT", "ETHUSDT"])
        retourne : dict { "high": df, "low": df, "close": df }
        """

        datasets = {
            "high": None,
            "low": None,
            "close": None
        }

        print(f"[{self.interval}] Fetching {len(symbols)} symbols")

        for symbol in symbols:
            try:
                print(f"[{self.interval}] Fetch {symbol}")

                df = self.fetcher._fetch_klines3(
                    symbol,
                    interval=self.interval,
                    limit=self.limit
                )

                if df is None or df.empty:
                    continue

                # 🔹 Exclure la bougie en cours
                df = df.iloc[:-1]

                # 🔹 S'assurer que l'index est datetime
                df.index = pd.to_datetime(df.index)

                for price_type in datasets.keys():

                    if price_type not in df.columns:
                        continue

                    series = df[price_type].astype(float).copy()
                    series.name = symbol

                    if datasets[price_type] is None:
                        datasets[price_type] = series.to_frame()
                    else:
                        datasets[price_type] = datasets[price_type].join(
                            series, how="outer"
                        )

                time.sleep(sleep_between_symbols)

            except Exception as e:
                print(f"[{self.interval}] Error {symbol}: {e}")

        return datasets