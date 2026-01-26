import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CAnalyse1000:

    def __init__(self, lookback=1000):
        self.lookback = lookback

    # =========================================================
    # Utils
    # =========================================================
    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    # =========================================================
    # Détection casse MA (fonction existante)
    # =========================================================
    def detecte_casse_ma(
        self,
        df: pd.DataFrame,
        ma_period: int,
        nb_minutes_before: int,
        prct_below_max: float,   # conservé dans l’interface, non utilisé ici
        verbose: bool = True
    ):
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
        ma_now = df["ma"].iloc[-1]

        crit_1 = low_now < ma_now * 0.995 and close_now < ma_now

        # -----------------------------
        # 2) Dernier close > MA
        # -----------------------------
        df_sup = df[df["close"] > df["ma"]]

        if df_sup.empty:
            if verbose:
                print("❌ Aucun close > MA trouvé")
            return False

        # -----------------------------
        # 2bis) Doit dater de moins de 10 minutes
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
        end_pos = pos_last_sup

        if start_pos < 0:
            return False

        df_zone = df.iloc[start_pos:end_pos]

        nb_close_below = (df_zone["close"] < df_zone["ma"]).sum()
        crit_3 = nb_close_below == 0

        # -----------------------------
        # 4) Low sous MA dans la zone
        # -----------------------------
        count_low_under_ma = (df_zone["low"] < df_zone["ma"]).sum()
        crit_4 = count_low_under_ma > 0

        if verbose:
            date_str = (
                idx_last_sup.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(idx_last_sup, "strftime")
                else str(idx_last_sup)
            )

            print(
                f"[detecte_casse_ma] "
                f"C1(close<MA*0.995)={crit_1} | "
                f"C3(nb_close_below={nb_close_below}) | "
                f"C4(low<MA)={count_low_under_ma} | "
                f"idx_last_sup={date_str} | "
                f"val_ma_last_sup={df_sup['ma'].iloc[-1]:.3e}"
            )

        return crit_1 and crit_3 and crit_4, df_sup["ma"].iloc[-1]

    # =========================================================
    # Détection atteinte MA + RSI
    # =========================================================
    def detecte_atteint_ma(
        self,
        df: pd.DataFrame,
        ma_period: int,
        verbose: bool = True
    ) -> bool:
        """
        Conditions :
        1) Dernier high < MA
           ET dernier high > 0.995 * MA
        2) RSI 5 > 80, RSI 9 > 70, RSI 14 > 65
        """

        # -----------------------------
        # Préparation
        # -----------------------------
        df = df.iloc[-self.lookback:].copy()

        if len(df) < max(ma_period, 14) + 2:
            return False

        df["ma"] = df["close"].rolling(ma_period).mean()
        df["rsi_5"] = self._compute_rsi(df["close"], 5)
        df["rsi_9"] = self._compute_rsi(df["close"], 9)
        df["rsi_14"] = self._compute_rsi(df["close"], 14)

        last = df.iloc[-1]

        if pd.isna(last["ma"]) or pd.isna(last["rsi_14"]):
            return False

        # -----------------------------
        # Condition 1 : high proche MA
        # -----------------------------
        high_now = last["high"]
        ma_now = last["ma"]

        crit_1 = high_now < ma_now and high_now > 0.995 * ma_now

        # -----------------------------
        # Condition 2 : RSI élevés
        # -----------------------------
        crit_2 = (
            last["rsi_5"] > 80 and
            last["rsi_9"] > 70 and
            last["rsi_14"] > 65
        )

        if verbose:
            print(
                f"[detecte_atteint_ma] "
                f"C1(high≈MA)={crit_1} | "
                f"RSI5={last['rsi_5']:.1f} "
                f"RSI9={last['rsi_9']:.1f} "
                f"RSI14={last['rsi_14']:.1f}"
            )

        return crit_1 and crit_2
