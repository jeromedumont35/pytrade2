import os
import glob
import pandas as pd
from datetime import datetime


# ==========================================================
# GLOBAL DATABASE
# ==========================================================
DB = {}


class CPriceDatabase:

    EXT = ".csv"

    def __init__(self):
        pass

    # ======================================================
    # SAVE DATASETS
    # ======================================================
    def save(self, datasets: dict, resolution: str):

        prefix = f"data_{resolution}_"

        # Supprimer anciens fichiers de cette résolution
        for f in glob.glob(f"{prefix}*{self.EXT}"):
            os.remove(f)

        for price_type, df in datasets.items():

            if df is None or df.empty:
                continue

            # 🔥 Dates récentes en haut dans le fichier
            df_to_save = df.sort_index(ascending=False)

            ts = datetime.utcnow().strftime("%Y_%m_%dT%H%M")
            filename = f"{prefix}{price_type}_{ts}{self.EXT}"

            df_to_save.to_csv(
                filename,
                sep=";",
                float_format="%.3e"
            )

            print(f"[{resolution}] Saved {filename}")

    # ======================================================
    # LOAD INTO DB
    # ======================================================
    def load(self, resolution: str):

        global DB

        prefix = f"data_{resolution}_"

        datasets = {}

        for price_type in ["high", "low", "close"]:

            files = glob.glob(f"{prefix}{price_type}_*{self.EXT}")

            if not files:
                continue

            latest_file = max(files, key=os.path.getctime)

            df = pd.read_csv(
                latest_file,
                sep=";",
                index_col=0
            )

            df.index = pd.to_datetime(df.index)

            # 🔥 Remettre en ordre chronologique
            df.sort_index(inplace=True)

            datasets[price_type] = df

        # ==================================================
        # Reconstruction DB[symbol][(resolution, price_type)]
        # ==================================================
        for price_type, df in datasets.items():

            for symbol in df.columns:

                series = df[symbol].astype(float)

                if symbol not in DB:
                    DB[symbol] = pd.DataFrame(index=series.index)

                DB[symbol][(resolution, price_type)] = series

        # 🔥 Nettoyage MultiIndex
        for symbol in DB:

            DB[symbol].columns = pd.MultiIndex.from_tuples(
                DB[symbol].columns
            )

            DB[symbol].sort_index(axis=1, inplace=True)
            DB[symbol].sort_index(inplace=True)

        print(f"[{resolution}] DB updated")

        return DB