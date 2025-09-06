import time
import argparse
from datetime import datetime, timedelta, timezone
from downloader import CBinanceDataFetcher
import CTradingAlgo
import pandas as pd
import CEvaluateROI
import requests
from orders import COrders_Bitget

def test_internet_connection(timeout=3):
    """
    Teste si on est connecté à Internet.
    Retourne True si OK, False sinon.
    """
    try:
        requests.get("https://www.google.com", timeout=timeout)
        return True
    except requests.RequestException:
        return False

def lire_identifiants(filepath: str) -> dict:
    """
    Récupère les identifiants API (clé, secret, mot de passe) stockés
    sur les 3 premières lignes d’un fichier texte.

    :param filepath: chemin complet + nom du fichier
    :return: dict avec {api_key, api_secret, password}
    """
    creds = {"api_key": None, "api_secret": None, "password": None}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lignes = f.readlines()

        if len(lignes) < 3:
            raise ValueError("⚠️ Le fichier doit contenir au moins 3 lignes.")

        creds["api_key"] = lignes[0].strip()
        creds["api_secret"] = lignes[1].strip()
        creds["password"] = lignes[2].strip()

    except FileNotFoundError:
        print(f"❌ Fichier introuvable: {filepath}")
    except Exception as e:
        print(f"⚠️ Erreur: {e}")

    return creds

def display_last_indicators_with_state(symbol_dfs: dict, original_cols: list, algo: CTradingAlgo):
    """
    Affiche un tableau des dernières valeurs d'indicateurs pour chaque symbole,
    avec la colonne 'State' après le symbole.
    Ne montre que les colonnes qui contiennent au moins une valeur non-NaN.
    """
    # Récupère l'état courant de chaque symbole depuis la stratégie
    states = algo.get_symbol_states()

    rows = []
    for sym, df in symbol_dfs.items():
        last_row = df.tail(1)
        # Colonnes ajoutées par apply_indicators
        new_cols = [c for c in df.columns if c not in original_cols]

        # Ne garder que les colonnes avec au moins une valeur non-NaN
        filtered_cols = [col for col in new_cols if not last_row[col].isna().all()]

        row_data = {"Symbol": sym, "State": states.get(sym, "UNKNOWN")}
        for col in filtered_cols:
            row_data[col] = last_row.iloc[0][col]
        rows.append(row_data)

    df_display = pd.DataFrame(rows)
    print("\n📊 Dernière bougie avec indicateurs appliqués et état :")
    print(df_display.to_string(index=False))



def align_df_to_new(df_sym: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """
    Supprime dans df_sym toutes les colonnes qui n'existent pas dans df_new.
    Retourne un DataFrame allégé qui a les mêmes colonnes que df_new.
    """
    common_cols = [c for c in df_sym.columns if c in df_new.columns]
    return df_sym[common_cols]

def main():
    # === PARAMÈTRES ===
    symbols = [
        "ATOMUSDC",
        "PENGUUSDC",  # tu peux en commenter certains
        "SOLUSDC"
    ]

    interval = "1m"
    days = 10
    MAX_RETRY = 5  # Nombre max de tentatives avant d'abandonner

    # Parses arugments
    parser = argparse.ArgumentParser(description="Pytrade.")
    parser.add_argument("api_key", type=str, help="API key file")
    args = parser.parse_args()

    # Création de l'évaluateur
    evaluator = CEvaluateROI.CEvaluateROI(1000,trading_fee_rate=0.000)
    identifiants = lire_identifiants(args.api_key)
    print(identifiants)
    trader = COrders_Bitget.COrders_Bitget(identifiants["api_key"], identifiants["api_secret"], identifiants["password"])

    # === INITIALISATION ===
    fetcher = CBinanceDataFetcher.BinanceDataFetcher()
    algo = CTradingAlgo.CTradingAlgo(l_interface_trade=trader, risk_per_trade_pct=0.2, strategy_name="RSI5min30")

    # === 1. Téléchargement et simulation historique ===
    print("📥 Téléchargement de l’historique...")
    df_hist = fetcher.get_historical_klines(symbols, interval=interval, days=days)

    # Préparation des DataFrames par symbole
    symbol_dfs = {}
    for sym in symbols:
        df_sym = df_hist[df_hist["symbol"] == sym].drop(columns=["symbol"])
        df_sym = algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))
        symbol_dfs[sym] = df_sym

    # Simulation historique complète
    list_data_hist = [(df, sym) for sym, df in symbol_dfs.items()]
    print("⚡ Exécution de la simulation historique...")
    algo.run(list_data_hist, execution=True)

    # === 2. Boucle temps réel ===
    print("🔄 Passage en mode production (temps réel)...")

    while True:
        now = datetime.now(timezone.utc)

        if now.second == 56:
            if not test_internet_connection(3):
                print("❌ Pas de connexion Internet. On quitte")
                break;
            else:
                print(f"✅ Connexion Internet OK. Heure UTC: {now}")

        if now.second == 0:
            print(f"\n⏰ Nouvelle minute détectée : {now}")
            time.sleep(3)  # Laisser Binance publier la bougie



            # Récupération dernière bougie complète
            df_last = fetcher.get_last_complete_kline(symbols, interval=interval)

            if df_last.empty:
                print("⚠️ Pas de nouvelle bougie dispo (retard API ?).")
                time.sleep(1)
                continue

            list_data_last = []

            for sym in symbols:
                df_sym = symbol_dfs[sym]

                # Extraire la dernière bougie Binance
                df_new = df_last[df_last["symbol"] == sym].drop(columns=["symbol"])

                # Aligner df_sym sur les colonnes de df_new
                df_sym = align_df_to_new(df_sym, df_new)

                # ======= DETECTION ET COMBLEMENT DES GAPS =======
                # Vérifie s'il y a un gap entre la dernière bougie DF et df_new
                if not df_sym.empty:
                    last_time = df_sym.index[-1]
                    new_time = df_new.index[-1]
                    expected_time = last_time + timedelta(minutes=1)

                    if expected_time < new_time:
                        print(f"⚠️ Gap détecté pour {sym}: {expected_time} -> {new_time}")
                        # Générer des bougies "fictives" avec close = dernière close connue
                        n_missing = int((new_time - expected_time).total_seconds() / 60)
                        for i in range(n_missing):
                            missing_time = expected_time + timedelta(minutes=i)
                            missing_row = df_sym.iloc[[-1]].copy()
                            missing_row.index = [missing_time]
                            df_sym = pd.concat([df_sym, missing_row])

                # print("\n=== DEBUG DATES ===")
                # print(f"Symbole: {sym}")
                # print("Index df_sym avant concat:")
                # print(df_sym.index[-5:])  # les 5 dernières dates
                #
                # print("Index df_new:")
                # print(df_new.index)

                # Vérifie si des doublons existent déjà dans df_sym
                dups = df_sym.index[df_sym.index.duplicated()]
                if not dups.empty:
                    print("⚠️ Doublons détectés dans df_sym:", dups)

                df_sym = pd.concat([df_sym.iloc[1:], df_new])

                # Nettoyage : doublons et tri par index
                # df_sym = df_sym[~df_sym.index.duplicated(keep='last')]
                # df_sym = df_sym.sort_index()

                # Réappliquer les indicateurs sur tout df_sym
                original_cols = df_sym.columns.tolist()
                df_sym = algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))

                # Mise à jour mémoire
                symbol_dfs[sym] = df_sym

                # ⚡ On ne garde que la dernière bougie enrichie pour le run
                df_last_with_ind = df_sym.tail(1)
                list_data_last.append((df_last_with_ind, sym))

            # Exécution algo uniquement sur la dernière bougie
            algo.run(list_data_last, execution=True)

            display_last_indicators_with_state(symbol_dfs, original_cols,algo)


        time.sleep(0.5)

if __name__ == "__main__":
    main()

