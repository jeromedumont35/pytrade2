import pandas as pd
from datetime import datetime, timezone
import os

from FullTradingAlgo.surveillance.CLauncher import CLauncher


class CUpdateCSVSeuilMin:
    def __init__(self, filename, fetcher, interval="1m"):
        self.filename = filename
        self.fetcher = fetcher
        self.interval = interval
        self.launcher = CLauncher()

        # nom du fichier mis à jour
        base, ext = os.path.splitext(filename)
        self.output_filename = base + "_updated" + ext

    @staticmethod
    def parse_date(date_str):
        """Parse une date au format JJ/MM/YYYY_HH (naïve)."""
        if date_str == "0" or str(date_str).strip() == "":
            return None
        return datetime.strptime(date_str, "%d/%m/%Y_%H")

    def compute_linear_value(self, t0, v0, t1, v1, t_now):
        total_sec = (t1 - t0).total_seconds()
        if total_sec == 0:
            return v0
        alpha = (t_now - t0).total_seconds() / total_sec
        return v0 + alpha * (v1 - v0)

    def fetch_current_prices(self, symbols):
        """Récupère les derniers prix via le fetcher."""
        df_last = self.fetcher.get_last_complete_kline(symbols, interval=self.interval)

        # df_last doit contenir : symbol | close
        prices = {row["symbol"]: float(row["close"]) for _, row in df_last.iterrows()}
        return prices

    def update_file(self):
        df = pd.read_csv(self.filename, sep=';')

        # temps UTC actuel (sans secondes)
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now = now_utc.replace(tzinfo=None)

        # ─────────────────────────────
        #  1. Interpolation seuil_minu
        # ─────────────────────────────

        for idx, row in df.iterrows():

            if str(row['date0']) == "0" or float(row['val0']) == 0:
                continue

            t0 = self.parse_date(row['date0'])
            t1 = self.parse_date(row['date1'])

            if t0 is None or t1 is None:
                continue

            v0 = float(row['val0'])
            v1 = float(row['val1'])

            new_value = self.compute_linear_value(t0, v0, t1, v1, now)

            df.at[idx, 'seuil_minu'] = new_value

        # ─────────────────────────────
        #  2. Récupération des prix courant
        # ─────────────────────────────

        symbols = list(df["symbol"])
        prices = self.fetch_current_prices(symbols)

        print("\n====== DÉTAIL DES VARIATIONS (%) ======\n")

        # ─────────────────────────────
        #  3. Calcul des pourcentages
        # ─────────────────────────────

        for idx, row in df.iterrows():
            symbol = row["symbol"]
            seuil_minu = float(row["seuil_minu"])

            if seuil_minu == 0 or symbol not in prices:
                continue

            price_now = prices[symbol]

            pct = ((price_now - seuil_minu) / seuil_minu) * 100

            print(f"{symbol:20s} | prix actuel = {price_now:.6f} | seuil = {seuil_minu:.6f} | Δ = {pct:+.2f}%")

        print("\n========================================\n")

        # ─────────────────────────────
        #  4. Sauvegarde du fichier
        # ─────────────────────────────
        df.to_csv(self.output_filename, sep=';', index=False)

        self.launcher.run_launcher(6, "LABUSDT", 1)

        return self.output_filename
