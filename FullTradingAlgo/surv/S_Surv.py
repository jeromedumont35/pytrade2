#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from datetime import datetime, timezone
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CLauncher2 import CLauncher2
from FullTradingAlgo.downloader import CBitgetDataFetcher


CSV_PATH = "Entry.csv"
INTERVAL = "1m"


class CheckCSVEntryOnly:
    def __init__(self, filename, fetcher, interval="1m"):
        self.filename = filename
        self.fetcher = fetcher
        self.interval = interval
        self.launcher = CLauncher2()

        # 🔒 Mémoire des symboles déjà lancés
        self.already_launched = set()

    # =================================================
    # 📄 CSV
    # =================================================
    def load_csv(self) -> pd.DataFrame:
        return pd.read_csv(self.filename, sep=";", dtype=str)

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
    def check_and_launch(
        self,
        amount: float = 6,
        nb_days: int = 1,
        trigger_pct: float = -3.0
    ):
        df = self.load_csv()

        now = (
            datetime.now(timezone.utc)
            .replace(second=0, microsecond=0)
            .replace(tzinfo=None)
        )

        # -------------------------------
        # Entries valides uniquement
        # -------------------------------
        entries = {}
        for _, row in df.iterrows():
            try:
                entry = float(row["entry"])
            except Exception:
                continue

            if entry > 0:
                entries[row["symbol"]] = entry

        if not entries:
            print("Aucune entry valide trouvée.")
            return

        prices = self.fetch_current_prices(list(entries.keys()))

        print("\n====== CHECK ENTRY (%) ======\n")

        for symbol, entry in entries.items():

            if symbol not in prices:
                continue

            price_now = prices[symbol]
            pct = ((price_now - entry) / entry) * 100

            print(
                f"{symbol:20s} | "
                f"prix = {price_now:.8f} | "
                f"entry = {entry:.8f} | "
                f"Δ = {pct:+.2f}%"
            )

            if self.should_trigger(symbol, pct, trigger_pct):
                self.trigger_bot(symbol, amount, nb_days, pct)

        print("\n=================================\n")


# =====================================================
# 🚀 EXEC
# =====================================================
if __name__ == "__main__":
    fetcher = CBitgetDataFetcher.BitgetDataFetcher()

    checker = CheckCSVEntryOnly(
        filename=CSV_PATH,
        fetcher=fetcher,
        interval=INTERVAL
    )

    checker.check_and_launch(
        amount=6,
        nb_days=1,
        trigger_pct=-3.0
    )
