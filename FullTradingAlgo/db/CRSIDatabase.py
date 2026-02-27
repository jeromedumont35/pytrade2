import os
import glob
import pandas as pd
from datetime import datetime

# ==========================================================
# GLOBAL DATABASE
# ==========================================================
DB = {}

class CRSIDatabase:

    EXT = ".csv"

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI
    # ======================================================
    @staticmethod
    def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def save_rsi_from_data(self, data: dict, resolution: str, rsi_period: int):
        df_close = data.get("close")
        if df_close is None or df_close.empty:
            print(f"No close data to compute RSI")
            return None

        prefix = f"data_{resolution}_"

        # Supprimer anciens fichiers RSI pour cette période
        pattern = f"{prefix}rsi{rsi_period}_*{self.EXT}"
        for f in glob.glob(pattern):
            os.remove(f)

        # 🔹 Calcul RSI pour tous les symboles
        df_rsi = pd.DataFrame(index=df_close.index)
        for symbol in df_close.columns:
            df_rsi[symbol] = self.compute_rsi(df_close[symbol], rsi_period)

        # 🔹 Trier dates récentes en haut
        df_rsi_to_save = df_rsi.sort_index(ascending=False)

        ts = datetime.utcnow().strftime("%Y_%m_%dT%H%M")
        filename = f"{prefix}rsi{rsi_period}_{ts}.csv"

        df_rsi_to_save.to_csv(
            filename,
            sep=";",
            float_format="%.1f"  # 1 chiffre après la virgule
        )
        print(f"[{resolution}] Saved {filename}")

        return df_rsi

    # ======================================================
    # LOAD RSI INTO DB
    # ======================================================
    def load_rsi(self, resolution: str, rsi_period: int):
        global DB

        prefix = f"data_{resolution}_"
        price_type = f"RSI{rsi_period}"

        files = glob.glob(f"{prefix}rsi{rsi_period}_*{self.EXT}")
        if not files:
            print(f"[{resolution}] Aucun fichier RSI{rsi_period} trouvé")
            return DB

        latest_file = max(files, key=os.path.getctime)

        df = pd.read_csv(latest_file, sep=";", index_col=0)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Reconstruction DB
        for symbol in df.columns:
            series = df[symbol].astype(float)
            if symbol not in DB:
                DB[symbol] = pd.DataFrame(index=series.index)
            DB[symbol][(resolution, price_type)] = series

        # Nettoyage MultiIndex
        for symbol in DB:
            DB[symbol].columns = pd.MultiIndex.from_tuples(DB[symbol].columns)
            DB[symbol].sort_index(axis=1, inplace=True)
            DB[symbol].sort_index(inplace=True)

        print(f"[{resolution}] DB updated with {price_type}")
        return DB