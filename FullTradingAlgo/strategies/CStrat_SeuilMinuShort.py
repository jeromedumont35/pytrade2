import pandas as pd
import numpy as np
import sys, os
from enum import Enum, auto
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import CTransformToPanda


class StratState(Enum):
    IDLE = auto()


class CStrat_SeuilMinuShort:

    def __init__(self,
                 interface_trade=None,
                 risk_per_trade_pct: float = 0.1,
                 csv_path: str = "../../surveillance/LauncherListe_updated.csv"):

        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.csv_path = csv_path

        # Chargement CSV
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV introuvable : {csv_path}")

        self.df_file = pd.read_csv(csv_path, sep=';')

        # Nettoyage basique
        self.df_file.columns = self.df_file.columns.str.strip()

        self.transformer = CTransformToPanda.CTransformToPanda(
            raw_dir="../raw",
            panda_dir="../panda"
        )

        self.state = {}

    # ======================================================
    # 🕒 Utils temps
    # ======================================================
    @staticmethod
    def parse_date(date_str):
        """Parse une date au format JJ/MM/YYYY_HH (naïve)."""
        if date_str is None:
            return None
        date_str = str(date_str).strip()
        if date_str == "" or date_str == "0":
            return None
        return datetime.strptime(date_str, "%d/%m/%Y_%H")

    @staticmethod
    def compute_linear_value(t0, v0, t1, v1, t_now):
        total_sec = (t1 - t0).total_seconds()
        if total_sec == 0:
            return v0
        alpha = (t_now - t0).total_seconds() / total_sec
        return v0 + alpha * (v1 - v0)

    # ======================================================
    # 📊 Indicators (placeholder)
    # ======================================================
    def apply_indicators(self, df, is_btc_file):
        return df.copy()

    # ======================================================
    # 🚀 Application stratégie
    # ======================================================
    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []

        if blocked:
            return actions

        # index courant
        i = df.index.get_loc(timestamp)

        # Annulation ordres ouverts
        if self.interface_trade is not None:
            self.interface_trade.cancel_all_open_orders(symbol)

        # temps UTC actuel (minute près)
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now = now_utc.replace(tzinfo=None)

        # ==================================================
        # 🔍 Récupération ligne CSV correspondant au symbole
        # ==================================================
        df_sym = self.df_file[self.df_file["symbol"] == symbol]

        if df_sym.empty:
            return actions  # aucun seuil défini pour ce symbole

        csv_row = df_sym.iloc[0]

        # ==================================================
        # 📐 Calcul de la valeur courante interpolée
        # ==================================================
        t0 = self.parse_date(csv_row.get("date0"))
        t1 = self.parse_date(csv_row.get("date1"))

        if t0 is None or t1 is None:
            return actions

        try:
            v0 = float(csv_row.get("val0"))
            v1 = float(csv_row.get("val1"))
        except (TypeError, ValueError):
            return actions

        current_value = self.compute_linear_value(
            t0=t0,
            v0=v0,
            t1=t1,
            v1=v1,
            t_now=now
        )

        # ==================================================
        # 📥 Action trading
        # ==================================================
        actions.append({
            "action": "OPEN",
            "symbol": symbol,
            "side": "SHORT",
            "price": current_value,
            "sl": [],
            "usdc": self.risk_per_trade_pct,
            "reason": "PRICE_BELOW_TREND_-3pct",
            "entry_index": i
        })

        return actions
