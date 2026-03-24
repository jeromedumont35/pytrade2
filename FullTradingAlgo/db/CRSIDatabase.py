import os
import glob
import pandas as pd
from datetime import datetime

class CRSIDatabase:

    EXT = ".csv"

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI (VERSION WILDER AVEC RETOUR DES WEIGHTS)
    # ======================================================
    @staticmethod
    def compute_rsi_with_weights(series: pd.Series, period: int = 14):
        """
        Calcule le RSI selon Wilder et retourne aussi avg_gain et avg_loss
        """
        alpha = 1 / period

        delta = series.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=alpha, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=alpha, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.where(avg_loss != 0, 100)

        return rsi, avg_gain, avg_loss

    # ======================================================
    # SAVE RSI + WEIGHTS
    # ======================================================
    def save_rsi_from_data(self, data: dict, resolution: str, rsi_period: int):
        df_close = data.get("close")
        if df_close is None or df_close.empty:
            print("No close data to compute RSI")
            return None

        prefix = f"{resolution}_"

        # Supprimer anciens fichiers RSI pour cette période (weights inclus, sera recréé)
        pattern = f"{prefix}rsi{rsi_period}_2*{self.EXT}"
        for f in glob.glob(pattern):
            os.remove(f)

        df_rsi = pd.DataFrame(index=df_close.index)
        weights_rows = []

        for symbol in df_close.columns:
            series = df_close[symbol].dropna()
            if len(series) < rsi_period + 1:
                continue

            # ===== CALCUL RSI + WEIGHTS EN UNE PASSE =====
            rsi_series, avg_gain, avg_loss = self.compute_rsi_with_weights(series, rsi_period)
            df_rsi[symbol] = rsi_series

            # ===== DERNIER POIDS POUR CHARGEMENT RAPIDE =====
            weights_rows.append({
                "symbol": symbol,
                "avg_gain": avg_gain.iloc[-1],
                "avg_loss": avg_loss.iloc[-1],
                "last_close": series.iloc[-1]
            })

        # ===== SAVE RSI =====
        df_rsi_to_save = df_rsi.sort_index(ascending=False)
        ts = datetime.utcnow().strftime("%Y_%m_%dT%H%M")
        rsi_filename = f"{prefix}rsi{rsi_period}_{ts}.csv"
        df_rsi_to_save.to_csv(rsi_filename, sep=";", float_format="%.1f")
        print(f"[{resolution}] Saved RSI -> {rsi_filename}")

        # ===== SAVE WEIGHTS =====
        weights_filename = f"{prefix}rsi{rsi_period}_weights{self.EXT}"
        df_weights = pd.DataFrame(weights_rows)
        df_weights.to_csv(weights_filename, sep=";", index=False, float_format="%.10f")
        print(f"[{resolution}] Saved WEIGHTS -> {weights_filename}")

        return df_rsi

    # ======================================================
    # LOAD RSI INTO DB
    # ======================================================
    def load_rsi(self, resolution: str, rsi_period: int):
        DB = {}
        prefix = f"{resolution}_"
        price_type = f"RSI{rsi_period}"

        files = glob.glob(f"{prefix}rsi{rsi_period}_*{self.EXT}")
        if not files:
            print(f"[{resolution}] Aucun fichier RSI{rsi_period} trouvé")
            return DB

        latest_file = max(files, key=os.path.getctime)
        df = pd.read_csv(latest_file, sep=";", index_col=0)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        for symbol in df.columns:
            series = df[symbol].astype(float)
            if symbol not in DB:
                DB[symbol] = pd.DataFrame(index=series.index)
            DB[symbol][(resolution, price_type)] = series

        for symbol in DB:
            DB[symbol].columns = pd.MultiIndex.from_tuples(DB[symbol].columns)
            DB[symbol].sort_index(axis=1, inplace=True)
            DB[symbol].sort_index(inplace=True)

        print(f"[{resolution}] DB updated with {price_type}")
        return DB

    # ======================================================
    # LOAD RSI WEIGHTS INTO DICT
    # ======================================================
    def load_rsi_weights(self, resolution: str, rsi_period: int):
        prefix = f"{resolution}_"
        filename = f"{prefix}rsi{rsi_period}_weights{self.EXT}"

        if not os.path.exists(filename):
            print(f"[{resolution}] Aucun fichier WEIGHTS trouvé")
            return {}

        df = pd.read_csv(filename, sep=";")
        weights = {}

        for _, row in df.iterrows():
            weights[row["symbol"]] = {
                "avg_gain": float(row["avg_gain"]),
                "avg_loss": float(row["avg_loss"]),
                "last_close": float(row["last_close"])
            }

        print(f"[{resolution}] WEIGHTS loaded")
        return weights
