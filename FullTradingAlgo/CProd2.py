import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import warnings
import CTradingAlgo


class CProd2:
    def __init__(self, p_symbol, trader, p_amount, strategy_name, fetcher, interval="1m"):
        """
        Classe pour exécuter une stratégie de trading avec récupération des données,
        simulation historique et boucle en temps réel.

        :param symbol: le symbole à suivre
        :param trader: instance du trader (ex: COrders_Bitget)
        :param amount 
        :param strategy_name: nom de la stratégie utilisée
        :param fetcher: instance du fetcher (ex: BitgetDataFetcher)
        :param interval: intervalle de bougies (ex: "1m")
        """
        warnings.filterwarnings("ignore", message="The behavior of DataFrame concatenation.*")

        self.symbols = p_symbol
        self.trader = trader
        self.amount = p_amount
        self.strategy_name = strategy_name
        self.fetcher = fetcher
        self.interval = interval

        print(f"📈 Initialisation du AlgoRunner pour stratégie '{strategy_name}' sur {len(symbols)} symboles.")

        # Initialisation de l'algo principal
        self.algo = CTradingAlgo2.CTradingAlgo2(
            l_interface_trade=self.trader,
            strategy_name=self.strategy_name
        )

        self.symbol_dfs = {}

    @staticmethod
    def test_internet_connection(timeout=3):
        """Teste si on est connecté à Internet."""
        try:
            requests.get("https://www.google.com", timeout=timeout)
            return True
        except requests.RequestException:
            return False

    def run_realtime_loop(self):
        """Boucle principale temps réel."""
        print("🔄 Passage en mode production (temps réel)...")
        while True:
            now = datetime.now(timezone.utc)

            if now.second == 56:
                if not self.test_internet_connection(3):
                    print("❌ Pas de connexion Internet. On quitte.")
                    break
                else:
                    print(f"✅ Connexion Internet OK. Heure UTC: {now}")

            if now.second == 0:
                print(f"\n⏰ Nouvelle minute détectée : {now}")
                time.sleep(3)  # Attendre la publication de la bougie

                l_bougies = self.fetcher.get_last_complete_kline(self.symbols, interval=self.interval)

                if df_last.empty:
                    print("⚠️ Pas de nouvelle bougie dispo (retard API ?).")
                    time.sleep(1)
                    continue

                list_data_last = []

                for sym in self.symbols:
                    df_sym = self.symbol_dfs[sym]
                    df_new = df_last[df_last["symbol"] == sym].drop(columns=["symbol"])

                    df_new = self.extend_df_with_sym(df_sym, df_new)

                    # Gestion des gaps temporels
                    if not df_sym.empty:
                        last_time = df_sym.index[-1]
                        new_time = df_new.index[-1]
                        expected_time = last_time + timedelta(minutes=1)
                        if expected_time < new_time:
                            print(f"⚠️ Gap détecté pour {sym}: {expected_time} -> {new_time}")
                            n_missing = int((new_time - expected_time).total_seconds() / 60)
                            for i in range(n_missing):
                                missing_time = expected_time + timedelta(minutes=i)
                                missing_row = df_sym.iloc[[-1]].copy()
                                missing_row.index = [missing_time]
                                df_sym = pd.concat([df_sym, missing_row])

                    # Ajout nouvelle bougie
                    df_sym = pd.concat([df_sym.iloc[1:], df_new])

                    # Réappliquer indicateurs
                    df_sym = self.algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))
                    self.symbol_dfs[sym] = df_sym

                    df_last_with_ind = df_sym.tail(1)
                    list_data_last.append((df_last_with_ind, sym))

                # Exécution stratégie sur dernière bougie
                self.algo.run(bougies, execution=True)

            time.sleep(0.5)
