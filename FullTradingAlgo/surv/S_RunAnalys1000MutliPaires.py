from datetime import datetime
import sys
import os
import time
import requests
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from FullTradingAlgo.downloader import CBitgetDataFetcher
from CAnalyse1000 import CAnalyse1000


# =========================
# Récupération des symbols USDT Futures Bitget
# =========================
def get_usdt_futures_symbols(fetcher):
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
# CONFIG
# =========================
INTERVAL = "1m"
LIMIT = 1000
SLEEP_BETWEEN_SYMBOLS = 0.1
SLEEP_BETWEEN_LOOPS = 0

MA_PERIODS = [50, 100, 200, 250]

CSV_PATH = "Entry.csv"
CSV_COLUMNS = ["symbol", "entry", "tp1", "tp2", "tp3", "sl"]


# =========================
# CSV : écriture signal
# =========================
CSV_PATH = "Entry.csv"
CSV_COLUMNS = ["symbol", "entry", "date0", "val0", "date1", "val1", "ma"]

def write_signal_csv(symbol, val):
    # val formaté en scientifique 3 chiffres après le point
    entry_val = f"{val:.3e}"

    # Nouvelle ligne à écrire : dates et valeurs par défaut = 0
    new_row = {
        "symbol": symbol,
        "entry": entry_val,
        "date0": 0,
        "val0": 0,
        "date1": 0,
        "val1": 0,
        "ma": 0
    }

    if os.path.exists(CSV_PATH):
        # Lire le CSV existant avec le bon séparateur
        df_csv = pd.read_csv(CSV_PATH, sep=";")

        # Assurer toutes les colonnes existent
        for col in CSV_COLUMNS:
            if col not in df_csv.columns:
                df_csv[col] = 0

        # Supprimer ancienne ligne si le symbole existe déjà
        df_csv = df_csv[df_csv["symbol"] != symbol]

        # Ajouter la nouvelle ligne
        df_csv = pd.concat([df_csv, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df_csv = pd.DataFrame([new_row], columns=CSV_COLUMNS)

    # Écrire le CSV avec séparateur ;
    df_csv.to_csv(CSV_PATH, index=False, sep=";")



# =========================
# INIT
# =========================
fetcher = CBitgetDataFetcher.BitgetDataFetcher()
analyseur = CAnalyse1000()


# =========================
# BOUCLE PRINCIPALE
# =========================
while True:
    print("\n==============================")
    print("Nouvelle boucle :", datetime.now())
    print("==============================")

    SYMBOLS = get_usdt_futures_symbols(fetcher)

    if not SYMBOLS:
        print("⚠️ Aucun symbole récupéré")
        time.sleep(5)
        continue

    symbols_to_skip = set()

    for symbol in SYMBOLS:
        if symbol in symbols_to_skip:
            continue

        try:
            print(f"\n--- Analyse pour {symbol} ---")

            df = fetcher._fetch_klines3(
                symbol,
                interval=INTERVAL,
                limit=LIMIT
            )

            if df is None or df.empty:
                print(f"Pas de données pour {symbol}")
                continue

            for col in ["close", "low"]:
                if col not in df.columns:
                    print(f"Colonne '{col}' manquante pour {symbol}")
                    continue

            for ma_period in MA_PERIODS:
                print(f"  ➜ Test MA{ma_period}")

                is_valid, val = analyseur.detecte_casse_ma(
                    df,
                    ma_period=ma_period,
                    prct_below_max=0.005,
                    nb_minutes_before=50,
                    verbose=True
                )

                if is_valid:
                    print(f"✅ SIGNAL détecté sur {symbol} (MA{ma_period})")

                    # écrire Entry.csv
                    write_signal_csv(symbol, val)

                    # ne plus retester ce symbole
                    symbols_to_skip.add(symbol)

                    # stop boucle MA
                    break

            time.sleep(SLEEP_BETWEEN_SYMBOLS)

        except Exception as e:
            print(f"❌ Erreur sur {symbol} : {e}")

    time.sleep(SLEEP_BETWEEN_LOOPS)
