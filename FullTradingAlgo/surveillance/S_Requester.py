import argparse
from datetime import datetime, timedelta, timezone
import sys
import os
import time
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.downloader import CBitgetDataFetcher

CSV_PATH = "LauncherListe.csv"


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


def update_csv(symbol: str, mean_close: float):
    columns = [
        "symbol",
        "seuil_49day",
        "date0",
        "val0",
        "date1",
        "val1",
        "seuil_minu",
    ]

    seuil_49day_str = f"{mean_close:.3e}"

    if os.path.exists(CSV_PATH):
        df = pd.read_csv(
            CSV_PATH,
            sep=";",
            dtype={"seuil_49day": str}
        )
    else:
        df = pd.DataFrame(columns=columns)

    if symbol in df["symbol"].values:
        df.loc[df["symbol"] == symbol, columns[1:]] = [
            seuil_49day_str, 0, 0, 0, 0, 0
        ]
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [[symbol, seuil_49day_str, 0, 0, 0, 0, 0]],
                    columns=columns,
                ),
            ],
            ignore_index=True,
        )

    df.to_csv(CSV_PATH, sep=";", index=False)



def compute_mean_close(fetcher, symbol, interval, nb_values):
    end_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    # N + 1 bougies demandées
    start_time = end_time - interval_to_timedelta(interval, nb_values + 1)

    df = fetcher._fetch_klines2(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time
    )

    if df is None or df.empty:
        print("❌ Aucune donnée récupérée")
        return

    df = df.tail(nb_values + 1)

    if len(df) < nb_values + 1:
        print("❌ Pas assez de bougies")
        return

    # ❌ on enlève la dernière bougie (incomplète)
    df = df.iloc[:-1]

    mean_close = df["close"].mean()

    print(
        f"🕒 {end_time.isoformat()} | "
        f"{symbol} | "
        f"mean_close={mean_close:.8e}"
    )

    update_csv(symbol, mean_close)


def main():
    parser = argparse.ArgumentParser(description="Calcul de moyenne des closes Bitget")
    parser.add_argument("symbol", type=str, help="Symbole (ex: BTCUSDT)")
    parser.add_argument("granularity", type=str, help="Granularité (1m, 5m, 1h, 1d, ...)")
    parser.add_argument("nb_values", type=int, help="Nombre de bougies utilisées")

    args = parser.parse_args()

    fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    # 🔁 MODE LIVE POUR 1m
    if args.granularity == "1m":
        print("⏳ Mode 1m actif – mise à jour CSV chaque minute")
        while True:
            now = datetime.now(timezone.utc)

            if now.second == 0:
                compute_mean_close(
                    fetcher,
                    args.symbol,
                    args.granularity,
                    args.nb_values
                )
                time.sleep(0.5)

            time.sleep(0.1)

    # ▶️ MODE ONE-SHOT
    else:
        compute_mean_close(
            fetcher,
            args.symbol,
            args.granularity,
            args.nb_values
        )


if __name__ == "__main__":
    main()
