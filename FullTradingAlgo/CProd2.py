import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import warnings
import CTradingAlgo2
import importlib


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

        try:
            # Import dynamique du module
            module = importlib.import_module(f"strategies.{self.strategy_name}")
            # Récupère la classe (même nom que strategy_name)
            strategy_class = getattr(module, self.strategy_name)
        except (ImportError, AttributeError):
            raise ValueError(f"Unknown strategy: {self.strategy_name}")

        # Instanciation
        self.strategy = strategy_class(
            self.interface_trade,
            self.risk_per_trade_pct,
        )

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

                l_bougies = self.fetcher._fetch_klines3(self.symbols, interval=self.interval,limit=1000)

                # Exécution stratégie sur dernière bougie
                self.algo.run(l_bougies, execution=True)

            time.sleep(0.5)
