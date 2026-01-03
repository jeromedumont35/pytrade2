import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Optional

from CLauncher import CLauncher


class CheckCSVSeuilMin:
    def __init__(self, filename, fetcher, interval="1m"):
        self.filename = filename
        self.fetcher = fetcher
        self.interval = interval
        self.launcher = CLauncher()

        # 🔒 Mémoire des symboles déjà lancés
        self.already_launched = set()

    # =================================================
    # 🧰 UTILS
    # =================================================
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        if date_str == "0" or str(date_str).strip() == "":
            return None
        return datetime.strptime(date_str, "%d/%m/%Y_%H")

    @staticmethod
    def compute_linear_value(
        t0: datetime, v0: float,
        t1: datetime, v1: float,
        t_now: datetime
    ) -> float:
        total_sec = (t1 - t0).total_seconds()
        if total_sec <= 0:
            return v0
        alpha = (t_now - t0).total_seconds() / total_sec
        return v0 + alpha * (v1 - v0)

    # =================================================
    # 📄 CSV
    # =================================================
    def load_csv(self) -> pd.DataFrame:
        return pd.read_csv(self.filename, sep=';')

    # =================================================
    # 📉 SEUILS
    # =================================================
    def build_thresholds(self, df: pd.DataFrame, now: datetime) -> Dict[str, float]:
        """
        Règle :
        - seuil_49day != 0 → seuil statique
        - sinon → interpolation date0/date1
        """
        seuils = {}

        for _, row in df.iterrows():
            symbol = row["symbol"]

            seuil_static = float(row["seuil_49day"])
            if seuil_static != 0:
                seuils[symbol] = seuil_static
                continue

            seuil_dynamic = self.compute_dynamic_threshold(row, now)
            if seuil_dynamic is not None:
                seuils[symbol] = seuil_dynamic

        return seuils

    def compute_dynamic_threshold(self, row, now: datetime) -> Optional[float]:
        if str(row["date0"]) == "0" or float(row["val0"]) == 0:
            return None

        t0 = self.parse_date(row["date0"])
        t1 = self.parse_date(row["date1"])

        if t0 is None or t1 is None:
            return None

        return self.compute_linear_value(
            t0,
            float(row["val0"]),
            t1,
            float(row["val1"]),
            now
        )

    # =================================================
    # 💰 PRICES
    # =================================================
    def fetch_current_prices(self, symbols):
        df_last = self.fetcher.get_last_complete_kline(
            symbols,
            interval=self.interval
        )

        return {
            row["symbol"]: float(row["close"])
            for _, row in df_last.iterrows()
        }

    # =================================================
    # 🚀 TRIGGER
    # =================================================
    def should_trigger(self, symbol: str, pct: float, trigger_pct: float) -> bool:
        if symbol in self.already_launched:
            print(f"--> {symbol} IGNORÉ (déjà lancé)")
            return False
        return pct > trigger_pct

    def trigger_bot(self, symbol: str, amount: float, nb_days: int, pct: float):
        print(f"--> TRIGGER BOT pour {symbol} (Δ {pct:.2f}%)")
        self.launcher.run_launcher(
            amount=amount,
            symbol=symbol,
            nb_days=nb_days
        )
        self.already_launched.add(symbol)

    # =================================================
    # 🧠 MAIN
    # =================================================
    def check_and_launch(self, amount=6, nb_days=1, trigger_pct=-3.0):

        df = self.load_csv()

        now = (
            datetime.now(timezone.utc)
            .replace(second=0, microsecond=0)
            .replace(tzinfo=None)
        )

        seuils = self.build_thresholds(df, now)

        if not seuils:
            print("Aucun seuil valide trouvé.")
            return

        prices = self.fetch_current_prices(list(seuils.keys()))

        print("\n====== CHECK SEUIL MIN (%) ======\n")

        for symbol, seuil in seuils.items():

            if seuil == 0 or symbol not in prices:
                continue

            price_now = prices[symbol]
            pct = ((price_now - seuil) / seuil) * 100

            print(
                f"{symbol:20s} | prix = {price_now:.8f} | "
                f"seuil = {seuil:.8f} | Δ = {pct:+.2f}%"
            )

            if self.should_trigger(symbol, pct, trigger_pct):
                self.trigger_bot(symbol, amount, nb_days, pct)

        print("\n=================================\n")
