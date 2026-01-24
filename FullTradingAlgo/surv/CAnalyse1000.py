import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CAnalyse1000:

    def __init__(self, lookback=1000):
        self.lookback = lookback

    def detecte_casse_ma(
        self,
        df: pd.DataFrame,
        ma_period: int,
        nb_minutes_before: int,
        prct_below_max: float,   # conservé dans l’interface, non utilisé ici
        verbose: bool = True
    ) -> bool:
        """
        Nouvelle logique :
        1) Dernier close < MA * 0.995
        2) Recherche depuis la fin du dernier close > MA (idx_last_sup)
        2bis) idx_last_sup doit dater de moins de 10 minutes
        3) Dans les nb_minutes_before avant idx_last_sup :
           - tous les closes > MA
           - au moins un low < MA
        """

        # -----------------------------
        # Préparation
        # -----------------------------
        df = df.iloc[-self.lookback:].copy()
        df["ma"] = df["close"].rolling(ma_period).mean()

        if len(df) < ma_period + nb_minutes_before + 2:
            return False

        # -----------------------------
        # 1) Dernière bougie sous MA * 0.995
        # -----------------------------
        low_now = df["low"].iloc[-1]
        close_now = df["close"].iloc[-1]
        ma_now    = df["ma"].iloc[-1]

        crit_1 = low_now < ma_now * 0.995 and close_now < ma_now

        # -----------------------------
        # 2) Dernier close > MA en remontant depuis la fin
        # -----------------------------
        df_sup = df[df["close"] > df["ma"]]

        if df_sup.empty:
            if verbose:
                print("❌ Aucun close > MA trouvé")
            return False

        # -----------------------------
        # 2bis) Dernier close > MA doit dater de moins de 10 minutes
        # -----------------------------
        last_df_time = df.index[-1]
        last_sup_time = df_sup.index[-1]

        if last_df_time - last_sup_time > pd.Timedelta(minutes=10):
            if verbose:
                print("❌ Dernier close > MA trop ancien (>10 min)")
            return False

        idx_last_sup = last_sup_time - pd.Timedelta(minutes=15)  # sécurité
        pos_last_sup = df.index.get_loc(idx_last_sup)

        # -----------------------------
        # 3) Zone avant idx_last_sup
        # -----------------------------
        start_pos = pos_last_sup - nb_minutes_before
        end_pos   = pos_last_sup

        if start_pos < 0:
            return False

        df_zone = df.iloc[start_pos:end_pos]

        # closes sous MA dans la zone
        nb_close_below = (df_zone["close"] < df_zone["ma"]).sum()
        crit_3 = nb_close_below == 0

        # -----------------------------
        # 4) low sous MA dans la zone
        # -----------------------------
        count_low_under_ma = (df_zone["low"] < df_zone["ma"]).sum()
        crit_4 = count_low_under_ma > 0

        # -----------------------------
        # Trace compacte sur une ligne
        # -----------------------------
        if verbose:
            date_str = idx_last_sup.strftime("%Y-%m-%d %H:%M:%S") \
                if hasattr(idx_last_sup, "strftime") else str(idx_last_sup)

            print(
                f"[detecte_casse_ma] "
                f"C1(close<MA*0.995)={crit_1} | "
                f"C3(nb_close_below={nb_close_below}) | "
                f"C4(low<MA)={count_low_under_ma} | "
                f"idx_last_sup={date_str} | "
                f"val_ma_last_sup={df_sup['ma'].iloc[-1]:.3e}"
            )

        return crit_1 and crit_3 and crit_4, df_sup["ma"].iloc[-1]
