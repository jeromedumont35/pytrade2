import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CFetcherMultiSymbols import CFetcherMultiSymbols
from FullTradingAlgo.downloader import CBitgetDataFetcher
from CPriceDatabase import CPriceDatabase
from CRSIDatabase import CRSIDatabase


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
    symbols = symbols[:100]

    print(f"Symbols utilisés ({len(symbols)}): {symbols}")

    # 🔹 Initialisation du fetcher
    fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    fetcher_multi = CFetcherMultiSymbols(
        fetcher=fetcher,
        interval=interval,
        limit=1000
    )

    # 🔹 Récupération des données
    data = fetcher_multi.fetch(symbols, sleep_between_symbols=0)

    # 🔹 Gestion base de données
    db_price = CPriceDatabase()

    # 1️⃣ Sauvegarde CSV
    db_price.save(data, interval)

    # 2️⃣ Chargement dans DB
    DB = db_price.load(interval)

    # 3️⃣ Exemple d’accès : premier symbole de la liste
    first_symbol = symbols[0]
    btc_close = DB[first_symbol][(interval, "close")]
    btc_high = DB[first_symbol][(interval, "high")]

    print(f"{first_symbol} - dernier close: {btc_close.iloc[-1]}")
    print(f"{first_symbol} - dernier high: {btc_high.iloc[-1]}")

    rsi_period = 5

    db_rsi = CRSIDatabase()
    # 1️⃣ Calcul et sauvegarde RSI depuis data["close"]
    datasets_rsi = db_rsi.save_rsi_from_data(data, interval, rsi_period)

    # 2️⃣ Chargement dans DB
    DB = db_rsi.load_rsi(interval, rsi_period)

    # 3️⃣ Accès au RSI
    first_symbol = list(data["close"].columns)[0]
    rsi_series = DB[first_symbol][(interval, f"RSI{rsi_period}")]
    print(rsi_series.tail())




# ==========================================================
# EXECUTION
# ==========================================================
if __name__ == "__main__":
    main()