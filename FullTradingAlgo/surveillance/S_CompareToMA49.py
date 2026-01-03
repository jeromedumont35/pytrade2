import os
import pandas as pd
from FullTradingAlgo.surveillance.CGet50DaysHistory import CGet50DaysHistory


CSV_PATH = "LauncherListe.csv"


def select_pairs_close_to_ma49(top_n=10):
    getter = CGet50DaysHistory()
    df = getter.fetch(nb_days=50)

    if df.empty:
        print("❌ Aucun data récupéré")
        return pd.DataFrame()

    results = []

    for symbol, df_sym in df.groupby("symbol"):
        df_sym = df_sym.sort_index()

        # Sécurité : il faut bien 50 bougies
        if len(df_sym) < 50:
            continue

        # -------------------------
        # MA49 sur les 49 jours complets
        # -------------------------
        ma49 = df_sym.iloc[:-1]["close"].mean()
        last_close = df_sym.iloc[-1]["close"]

        # -------------------------
        # NOUVELLE RÈGLE :
        # Aucun HIGH au-dessus de la MA49
        # sur les 6 jours avant le dernier
        # -------------------------
        last_6_before = df_sym.iloc[-7:-1]

        if (last_6_before["high"] > ma49).any():
            continue

        # -------------------------
        # Distance à la MA49
        # -------------------------
        distance = abs(last_close - ma49)

        results.append({
            "symbol": symbol,
            "ma49": ma49,
            "close_last": last_close,
            "distance": distance
        })

    if not results:
        print("⚠️ Aucun symbole ne respecte les règles")
        return pd.DataFrame()

    df_res = (
        pd.DataFrame(results)
        .sort_values("distance")
        .head(top_n)
        .reset_index(drop=True)
    )

    return df_res


def     append_to_launcher_csv(df_res):
    rows = []

    for _, row in df_res.iterrows():
        rows.append({
            "symbol": row["symbol"],
            # notation scientifique avec 2 chiffres après le point
            "seuil_49day": f"{row['ma49']:.2e}",
            "date0": 0,
            "val0": 0,
            "date1": 0,
            "val1": 0,
            "seuil_minu": 0
        })

    df_out = pd.DataFrame(
        rows,
        columns=[
            "symbol",
            "seuil_49day",
            "date0",
            "val0",
            "date1",
            "val1",
            "seuil_minu"
        ]
    )

    file_exists = os.path.isfile(CSV_PATH)

    df_out.to_csv(
        CSV_PATH,
        sep=";",
        index=False,
        mode="a",
        header=not file_exists
    )

    print(f"✅ {len(df_out)} lignes ajoutées à {CSV_PATH}")



# ============================
# MAIN
# ============================
if __name__ == "__main__":
    df_selection = select_pairs_close_to_ma49(top_n=10)

    if not df_selection.empty:
        print("\n📊 Top 10 paires les plus proches de leur MA49")
        print(df_selection.to_string(index=False))

        append_to_launcher_csv(df_selection)
