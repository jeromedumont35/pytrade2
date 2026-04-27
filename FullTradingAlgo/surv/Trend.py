import os
import glob
import numpy as np
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

def get_touch_points(max_df, slope, intercept, threshold_pct):
    touches = []

    for i, (date, price) in enumerate(max_df["high"].items()):
        y_line = slope * i + intercept
        if price <= y_line and (y_line - price) / y_line <= threshold_pct:
            touches.append((date, price, y_line))

    return touches


def plot_resistance(df_slice, max_df, slope, intercept, touches, symbol):
    plt.figure(figsize=(14, 6))

    # Courbe high
    plt.plot(df_slice.index, df_slice["high"], label="High", alpha=0.4)

    # Max locaux
    plt.scatter(max_df.index, max_df["high"], color="blue", label="Max locaux")

    # Droite de résistance
    x = np.arange(len(max_df))
    y = slope * x + intercept
    plt.plot(max_df.index, y, color="red", linewidth=2, label="Résistance")

    # Touches
    if touches:
        t_dates = [t[0] for t in touches]
        t_prices = [t[1] for t in touches]
        plt.scatter(
            t_dates, t_prices,
            color="red", s=120, facecolors="none",
            label="Touches"
        )

    plt.title(f"{symbol} – Résistance détectée")
    plt.legend()
    plt.grid(True)
    plt.show()


# ==========================================================
# CHARGEMENT DU CSV HIGH (issu de CPriceHistoryTF)
# ==========================================================

def load_high_csv(timeframe="5m"):
    files = sorted(glob.glob(f"data_{timeframe}_high_*.csv"), reverse=True)

    if not files:
        raise FileNotFoundError("Aucun fichier data_*_high_*.csv trouvé")

    print(f"[LOAD] {files[0]}")

    return pd.read_csv(
        files[0],
        sep=";",
        index_col=0,
        parse_dates=True
    )


# ==========================================================
# DÉTECTION DES MAXIMUMS LOCAUX
# ==========================================================

def detect_local_maxima(df, NbPointsSans):
    """
    df : DataFrame avec colonne 'high'
    NbPointsSans : fenêtre d'exclusion autour du maximum
    """
    highs = df["high"].values
    dates = df.index

    maxima = []

    for i in range(NbPointsSans, len(highs) - NbPointsSans):
        center = highs[i]

        if (
            center >= highs[i - NbPointsSans:i].max()
            and center >= highs[i + 1:i + 1 + NbPointsSans].max()
        ):
            maxima.append((dates[i], center))

    if not maxima:
        return pd.DataFrame(columns=["high"])

    return pd.DataFrame(maxima, columns=["date", "high"]).set_index("date")


# ==========================================================
# CONSTRUCTION DE LA DROITE DE RÉSISTANCE
# ==========================================================

def build_resistance_line(max_df):
    """
    max_df : DataFrame des maximums locaux
    Retourne (slope, intercept) ou None
    """
    if len(max_df) < 2:
        return None

    # max local de référence : le plus haut
    ref_date = max_df["high"].idxmax()
    ref_pos = max_df.index.get_loc(ref_date)
    ref_price = max_df.loc[ref_date, "high"]

    best_slope = None
    best_intercept = None

    # Recherche des max plus récents (à droite)
    for date2, price2 in max_df.loc[ref_date:].iloc[1:].itertuples():
        pos2 = max_df.index.get_loc(date2)

        slope = (price2 - ref_price) / (pos2 - ref_pos)
        intercept = ref_price - slope * ref_pos

        # Tous les autres max doivent être sous la droite
        valid = True
        for i, price in enumerate(max_df["high"].values):
            y_line = slope * i + intercept
            if price > y_line:
                valid = False
                break

        if valid:
            # pente la moins prononcée (la plus plate)
            if best_slope is None or slope > best_slope:
                best_slope = slope
                best_intercept = intercept

    if best_slope is None:
        return None

    return best_slope, best_intercept


# ==========================================================
# COMPTAGE DES TOUCHES PROCHE DE LA DROITE
# ==========================================================

def count_touches(max_df, slope, intercept, threshold_pct=0.001):
    """
    threshold_pct = 0.001 → 0.1 %
    """
    touches = 0

    for i, price in enumerate(max_df["high"].values):
        y_line = slope * i + intercept

        if price <= y_line:
            if (y_line - price) / y_line <= threshold_pct:
                touches += 1

    return touches


# ==========================================================
# RECHERCHE GLISSANTE DANS LE PASSÉ (UN SYMBOL)
# ==========================================================

def detect_resistance_for_symbol(
    df,
    symbol,
    NbPointsSans,
    NbPointsRetour1,
    Pas,
    threshold_pct,
    show_plot=True
):
    n = 0

    while True:
        end = len(df) - n * Pas
        start = max(0, end - NbPointsRetour1)

        if start <= 0:
            return None

        df_slice = df.iloc[start:end]

        max_df = detect_local_maxima(df_slice, NbPointsSans)
        if len(max_df) < 2:
            n += 1
            continue

        line = build_resistance_line(max_df)
        if line is None:
            n += 1
            continue

        slope, intercept = line
        touches = get_touch_points(max_df, slope, intercept, threshold_pct)

        if len(touches) >= 2:
            if show_plot:
                plot_resistance(
                    df_slice, max_df, slope, intercept, touches, symbol
                )

            return {
                "touches": len(touches),
                "slope": slope
            }

        n += 1



# ==========================================================
# APPLICATION À TOUTES LES PAIRES
# ==========================================================

def detect_resistances_all_pairs(
    df_high_all,
    NbPointsSans=5,
    NbPointsRetour1=300,
    Pas=50,
    threshold_pct=0.001
):
    results = {}

    for symbol in df_high_all.columns:
        series = df_high_all[symbol].dropna()

        if len(series) < NbPointsRetour1:
            continue

        df = pd.DataFrame({"high": series.iloc[:-25]})

        res = detect_resistance_for_symbol(
            df,
            symbol,  # <-- important !
            NbPointsSans,
            NbPointsRetour1,
            Pas,
            threshold_pct,
            show_plot=True
        )

        if res:
            results[symbol] = res
            print(f"[OK] {symbol} | touches={res['touches']}")
        else:
            print(f"[--] {symbol}")

    return results


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    TIMEFRAME = "5m"

    NbPointsSans = 5          # fenêtre d'exclusion autour des max locaux
    NbPointsRetour1 = 75     # profondeur de recherche initiale
    Pas = 10                  # pas de recul progressif
    threshold_pct = 0.001     # 0.1 %

    df_high_all = load_high_csv(TIMEFRAME)

    results = detect_resistances_all_pairs(
        df_high_all,
        NbPointsSans,
        NbPointsRetour1,
        Pas,
        threshold_pct
    )

    print("\n===== RÉSISTANCES DÉTECTÉES =====")
    for symbol, info in results.items():
        print(symbol, info)
