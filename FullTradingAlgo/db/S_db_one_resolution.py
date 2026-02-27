import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CFetcherMultiSymbols import CFetcherMultiSymbols
from FullTradingAlgo.downloader import CBitgetDataFetcher
from CPriceDatabase import CPriceDatabase


# ==========================================================
# FONCTION POUR RÉCUPÉRER LES SYMBOLS USDT
# ==========================================================
def get_usdt_futures_symbols():
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


# ==========================================================
# MAIN
# ==========================================================
def main():

    # 🔹 Récupération de l’intervalle depuis les arguments
    if len(sys.argv) < 2:
        print("Usage : python script.py <interval>")
        print("Exemples : 1h | 15m | 4h")
        sys.exit(1)

    interval = sys.argv[1]

    # 🔹 Récupérer les symboles USDT et limiter à 5 pour test
    symbols = get_usdt_futures_symbols()
    symbols = symbols[:5]

    print(f"Symbols utilisés ({len(symbols)}): {symbols}")

    # 🔹 Initialisation du fetcher
    fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    fetcher_multi = CFetcherMultiSymbols(
        fetcher=fetcher,
        interval=interval,
        limit=1000
    )

    # 🔹 Récupération des données
    data = fetcher_multi.fetch(symbols)

    # 🔹 Gestion base de données
    db_manager = CPriceDatabase()

    # 1️⃣ Sauvegarde CSV
    db_manager.save(data, interval)

    # 2️⃣ Chargement dans DB
    DB = db_manager.load(interval)

    # 3️⃣ Exemple d’accès : premier symbole de la liste
    first_symbol = symbols[0]

    btc_close = DB[first_symbol][(interval, "close")]
    btc_high = DB[first_symbol][(interval, "high")]

    print(f"{first_symbol} - dernier close: {btc_close.iloc[-1]}")
    print(f"{first_symbol} - dernier high: {btc_high.iloc[-1]}")


# ==========================================================
# EXECUTION
# ==========================================================
if __name__ == "__main__":
    main()