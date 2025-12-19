import pandas as pd
from datetime import datetime, timezone

from CLauncher import CLauncher


class CheckCSVSeuilMin:
    def __init__(self, filename, fetcher, interval="1m"):
        self.filename = filename
        self.fetcher = fetcher
        self.interval = interval
        self.launcher = CLauncher()

        # 🔒 Mémoire des symboles déjà lancés
        self.already_launched = set()

    # -------------------------------------------------
    @staticmethod
    def parse_date(date_str):
        """Parse une date au format JJ/MM/YYYY_HH (naïve)."""
        if date_str == "0" or str(date_str).strip() == "":
            return None
        return datetime.strptime(date_str, "%d/%m/%Y_%H")

    # -------------------------------------------------
    def compute_linear_value(self, t0, v0, t1, v1, t_now):
        total_sec = (t1 - t0).total_seconds()
        if total_sec == 0:
            return v0
        alpha = (t_now - t0).total_seconds() / total_sec
        return v0 + alpha * (v1 - v0)

    # -------------------------------------------------
    def fetch_current_prices(self, symbols):
        """Récupère les derniers prix via le fetcher."""
        df_last = self.fetcher.get_last_complete_kline(
            symbols,
            interval=self.interval
        )

        return {
            row["symbol"]: float(row["close"])
            for _, row in df_last.iterrows()
        }

    # -------------------------------------------------
    def check_and_launch(self, amount=6, nb_days=1, trigger_pct=-14.0):
        """
        - Calcule seuil_minu interpolé (en mémoire)
        - Calcule la variation %
        - Lance le bot si variation <= trigger_pct
        - Ignore les symboles déjà lancés
        """

        df = pd.read_csv(self.filename, sep=';')

        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now = now_utc.replace(tzinfo=None)

        # ─────────────────────────────
        # 1. Calcul du seuil interpolé
        # ─────────────────────────────
        seuils = {}

        for _, row in df.iterrows():

            if str(row["date0"]) == "0" or float(row["val0"]) == 0:
                continue

            t0 = self.parse_date(row["date0"])
            t1 = self.parse_date(row["date1"])

            if t0 is None or t1 is None:
                continue

            v0 = float(row["val0"])
            v1 = float(row["val1"])

            seuils[row["symbol"]] = self.compute_linear_value(
                t0, v0, t1, v1, now
            )

        # ─────────────────────────────
        # 2. Récupération des prix
        # ─────────────────────────────
        prices = self.fetch_current_prices(list(seuils.keys()))

        print("\n====== CHECK SEUIL MIN (%) ======\n")

        # ─────────────────────────────
        # 3. Calcul variation + trigger
        # ─────────────────────────────
        for symbol, seuil_minu in seuils.items():

            if seuil_minu == 0 or symbol not in prices:
                continue

            price_now = prices[symbol]
            pct = ((price_now - seuil_minu) / seuil_minu) * 100

            print(
                f"{symbol:20s} | prix = {price_now:.6f} | "
                f"seuil = {seuil_minu:.6f} | Δ = {pct:+.2f}%"
            )

            # ⛔ Déjà lancé → on ignore
            if symbol in self.already_launched:
                print(f"--> {symbol} IGNORÉ (déjà lancé)")
                continue

            # 🔥 CONDITION DE LANCEMENT
            if pct > trigger_pct:
                print(
                    f"--> TRIGGER BOT pour {symbol} "
                    f"(Δ {pct:.2f}%)"
                )

                self.launcher.run_launcher(
                    amount=amount,
                    symbol=symbol,
                    nb_days=nb_days
                )

                # 🔐 Marquer comme lancé
                self.already_launched.add(symbol)

        print("\n=================================\n")
