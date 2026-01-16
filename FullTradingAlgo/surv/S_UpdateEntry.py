import os
import sys
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CRequester import CRequester


CSV_PATH = "Entry.csv"
DATE_FMT = "%d/%m/%Y_%H"


# ----------------------------------------------------------------------
# Utils
# ----------------------------------------------------------------------
def parse_ma(ma_str: str) -> tuple[str, int]:
    parts = ma_str.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Format MA invalide : {ma_str}")
    return parts[0], int(parts[1])


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, DATE_FMT).replace(tzinfo=timezone.utc)


def compute_linear_entry(
    date0: str,
    val0: str,
    date1: str,
    val1: str,
    now: datetime
) -> float | None:
    try:
        t0 = parse_date(date0)
        t1 = parse_date(date1)
        v0 = float(val0)
        v1 = float(val1)
    except Exception:
        return None

    if t1 <= t0:
        return None

    # temps en secondes
    dt_total = (t1 - t0).total_seconds()
    dt_now = (now - t0).total_seconds()

    slope = (v1 - v0) / dt_total
    return v0 + slope * dt_now


# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
def update_entry_csv():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"{CSV_PATH} introuvable")

    df = pd.read_csv(CSV_PATH, sep=";", dtype=str)

    requester = CRequester()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for idx, row in df.iterrows():
        symbol = row["symbol"]
        ma_str = row["ma"].strip()

        # ==============================================================
        # 🔹 CAS 1 : ENTRY PAR MOYENNE MOBILE
        # ==============================================================
        if ma_str != "0":
            try:
                interval, nb_values = parse_ma(ma_str)
            except Exception as e:
                print(f"❌ {symbol} | erreur MA : {e}")
                continue

            mean_close = requester.compute_mean_close(
                symbol=symbol,
                interval=interval,
                nb_values=nb_values
            )

            if mean_close is None:
                print(f"❌ {symbol} | données insuffisantes")
                continue

            df.at[idx, "entry"] = f"{mean_close:.3e}"

            print(
                f"🕒 {now.isoformat()} | {symbol} | "
                f"entry(MA)={mean_close:.3e} | {ma_str}"
            )

        # ==============================================================
        # 🔹 CAS 2 : ENTRY PAR PENTE TEMPORELLE
        # ==============================================================
        else:
            entry = compute_linear_entry(
                date0=row["date0"],
                val0=row["val0"],
                date1=row["date1"],
                val1=row["val1"],
                now=now
            )

            if entry is None:
                print(f"❌ {symbol} | calcul pente impossible")
                continue

            df.at[idx, "entry"] = f"{entry:.3e}"

            print(
                f"🕒 {now.isoformat()} | {symbol} | "
                f"entry(PENTE)={entry:.3e}"
            )

    df.to_csv(CSV_PATH, sep=";", index=False)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    update_entry_csv()
