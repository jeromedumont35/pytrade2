import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import warnings
import CTradingAlgo


class CProd:
    def __init__(self, symbols, days, trader, risk_per_trade_pct, strategy_name, fetcher, interval="1m"):
        """
        Classe pour exécuter une stratégie de trading avec récupération des données,
        simulation historique et boucle en temps réel.

        :param symbols: liste des symboles à suivre
        :param days: nombre de jours d'historique à télécharger
        :param trader: instance du trader (ex: COrders_Bitget)
        :param risk_per_trade_pct: risque par trade en pourcentage
        :param strategy_name: nom de la stratégie utilisée
        :param fetcher: instance du fetcher (ex: BitgetDataFetcher)
        :param interval: intervalle de bougies (ex: "1m")
        """
        warnings.filterwarnings("ignore", message="The behavior of DataFrame concatenation.*")

        self.symbols = symbols
        self.days = days
        self.trader = trader
        self.risk_per_trade_pct = risk_per_trade_pct
        self.strategy_name = strategy_name
        self.fetcher = fetcher
        self.interval = interval

        print(f"📈 Initialisation du AlgoRunner pour stratégie '{strategy_name}' sur {len(symbols)} symboles.")

        # Initialisation de l'algo principal
        self.algo = CTradingAlgo.CTradingAlgo(
            l_interface_trade=self.trader,
            risk_per_trade_pct=self.risk_per_trade_pct,
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

    @staticmethod
    def extend_df_with_sym(df_sym: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
        """Ajoute dans df_new les colonnes présentes dans df_sym mais absentes dans df_new."""
        missing_cols = [c for c in df_sym.columns if c not in df_new.columns]
        for col in missing_cols:
            df_new[col] = pd.NA
        return df_new

    @staticmethod
    def display_last_indicators_with_state(symbol_dfs: dict, algo):
        """Affiche les derniers indicateurs et l'état de chaque symbole."""
        states = algo.strategy.get_symbol_states()
        rows = []
        for sym, df in symbol_dfs.items():
            last_row = df.tail(1)
            displayed_cols = algo.strategy.get_main_indicator()
            row_data = {"Symbol": sym, "State": states.get(sym, "UNKNOWN")}
            for col in displayed_cols:
                row_data[col] = last_row.iloc[0][col]
            rows.append(row_data)

        df_display = pd.DataFrame(rows)
        print("\n📊 Dernière bougie avec indicateurs et état :")
        print(df_display.to_string(index=False))

    def prepare_historical_data(self):
        """Télécharge et prépare les données historiques."""
        print("📥 Téléchargement de l’historique...")
        df_hist = self.fetcher.get_historical_klines(self.symbols, interval=self.interval, days=self.days)

        for sym in self.symbols:
            df_sym = df_hist[df_hist["symbol"] == sym].drop(columns=["symbol"])
            df_sym = self.algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))
            self.symbol_dfs[sym] = df_sym

    def run_backtest(self):
        """Exécute une simulation historique complète."""
        print("⚡ Exécution de la simulation historique...")
        list_data_hist = [(df, sym) for sym, df in self.symbol_dfs.items()]
        self.algo.run(list_data_hist, execution=True)

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

                df_last = self.fetcher.get_last_complete_kline(self.symbols, interval=self.interval)

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
                self.algo.run(list_data_last, execution=True)
                self.display_last_indicators_with_state(self.symbol_dfs, self.algo)

            time.sleep(0.5)
