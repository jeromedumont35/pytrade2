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
# FONCTION : récupérer toutes les paires USDT futures Bitget
# =========================
# ============================
# Récupération des symbols USDT Futures
# ============================
def get_usdt_futures_symbols(fetcher):
    params = {
        "productType": "usdt-futures"
    }

    r = requests.get("https://api.bitget.com/api/v2/mix/market/contracts", params=params, timeout=10)
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

# =========================
# CONFIGURATION
# =========================
INTERVAL = "1m"
LIMIT = 1000
SLEEP_BETWEEN_SYMBOLS = 0.1   # pause entre chaque paire (API safe)
SLEEP_BETWEEN_LOOPS = 0      # pause entre chaque boucle globale

# =========================
# INIT
# =========================
fetcher = CBitgetDataFetcher.BitgetDataFetcher()
analyseur = CAnalyse1000()




# =========================
# BOUCLE INFINIE
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

    for symbol in SYMBOLS:
        try:
            print(f"\n--- Analyse pour {symbol} ---")

            df = fetcher._fetch_klines3(symbol, interval=INTERVAL, limit=LIMIT)

            if df is None or df.empty:
                print(f"Pas de données pour {symbol}")
                continue

            for col in ["close", "low"]:
                if col not in df.columns:
                    print(f"Colonne '{col}' manquante pour {symbol}")
                    continue

            is_valid = analyseur.detecte_casse_ma(
                df,
                ma_period=100,
                prct_below_max=0.005,
                nb_minutes_before=50,
                verbose=True
            )

            if is_valid:
                print(f"✅ SIGNAL détecté sur {symbol}")

            time.sleep(SLEEP_BETWEEN_SYMBOLS)

        except Exception as e:
            print(f"❌ Erreur sur {symbol} :", e)

    time.sleep(SLEEP_BETWEEN_LOOPS)
