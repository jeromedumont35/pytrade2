from datetime import datetime, timedelta, timezone
import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.downloader import CBitgetDataFetcher


class CRequester:
    def __init__(self):
        self.fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    @staticmethod
    def interval_to_timedelta(interval: str, nb: int) -> timedelta:
        if interval.endswith("m"):
            return timedelta(minutes=int(interval[:-1]) * nb)
        if interval.endswith("h"):
            return timedelta(hours=int(interval[:-1]) * nb)
        if interval.endswith("d"):
            return timedelta(days=int(interval[:-1]) * nb)
        if interval.endswith("w"):
            return timedelta(weeks=int(interval[:-1]) * nb)
        raise ValueError(f"Granularité non supportée : {interval}")

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    def compute_mean_close(
        self,
        symbol: str,
        interval: str,
        nb_values: int
    ) -> float | None:
        """
        Récupère les bougies via CBitgetDataFetcher et calcule
        la moyenne des closes en excluant la dernière bougie (incomplète).
        """
        end_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # N + 1 bougies demandées
        start_time = end_time - self.interval_to_timedelta(interval, nb_values + 1)

        df = self.fetcher._fetch_klines2(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time
        )

        if df is None or df.empty:
            return None

        df = df.tail(nb_values + 1)

        if len(df) < nb_values + 1:
            return None

        # ❌ suppression de la dernière bougie (incomplète)
        df = df.iloc[:-1]

        return df["close"].mean()
