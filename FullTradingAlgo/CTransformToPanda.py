# CTransformToPanda.py

import os
import pickle
import pandas as pd

class CTransformToPanda:
    def __init__(self, raw_dir="raw", panda_dir="panda"):
        self.raw_dir = raw_dir
        self.panda_dir = panda_dir
        os.makedirs(self.panda_dir, exist_ok=True)

    def _prepare_dataframe(self, candles):
        import pandas as pd

        if not candles or not isinstance(candles[0], (list, tuple)):
            raise ValueError("⛔ Données de bougies invalides ou vides")

        nb_cols = len(candles[0])

        # === BINANCE === (12 colonnes)
        if nb_cols == 12:
            df = pd.DataFrame(candles, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df.set_index("time", inplace=True)
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(
                float)

        # === BITGET === (8 colonnes)
        elif nb_cols == 8:
            df = pd.DataFrame(candles, columns=[
                "time", "open", "high", "low", "close",
                "volume", "quote_volume", "usd_volume"
            ])
            df["time"] = pd.to_datetime(df["time"].astype(float), unit="ms")
            df.set_index("time", inplace=True)
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(
                float)

        else:
            raise ValueError(f"⛔ Format de bougies inconnu : {nb_cols} colonnes (attendu 8 ou 12)")

        # Calcul colonne moyenne
        df["moy_l_h_e_c"] = (df["open"] + df["close"] + df["high"] + df["low"]) / 4

        return df[["open", "high", "low", "close", "volume", "moy_l_h_e_c"]]

    def process_all(self, apply_indicators_func):
        raw_files = [f for f in os.listdir(self.raw_dir) if f.endswith(".raw")]
        if not raw_files:
            print("❌ Aucun fichier .raw trouvé.")
            return

        for filename in raw_files:
            filepath = os.path.join(self.raw_dir, filename)
            print(f"📂 Traitement de : {filepath}")
            with open(filepath, "rb") as f:
                candles = pickle.load(f)

            if not candles:
                print("⚠️ Fichier vide.")
                continue

            df = self._prepare_dataframe(candles)
            df = apply_indicators_func(df,"BTC" in filename)

            base = os.path.basename(filepath).replace(".raw", ".panda")
            panda_path = os.path.join(self.panda_dir, base)

            with open(panda_path, "wb") as f:
                pickle.dump(df, f)

            print(f"✅ Sauvegardé : {panda_path} ({len(df)} lignes)\n")
