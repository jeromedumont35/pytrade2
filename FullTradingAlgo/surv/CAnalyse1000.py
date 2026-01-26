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
    # Détection casse MA
    # =========================================================
    def detecte_casse_ma(
        self,
        df: pd.DataFrame,
        ma_period: int,
        nb_minutes_before: int,
        prct_below_max: float,
        verbose: bool = True
    ):

        df = df.iloc[-self.lookback:].copy()
        df["ma"] = df["close"].rolling(ma_period).mean()

        if len(df) < ma_period + nb_minutes_before + 2:
            return False

        low_now = df["low"].iloc[-1]
        close_now = df["close"].iloc[-1]
        ma_now = df["ma"].iloc[-1]

        crit_1 = low_now < ma_now * 0.995 and close_now < ma_now

        df_sup = df[df["close"] > df["ma"]]
        if df_sup.empty:
            return False

        last_df_time = df.index[-1]
        last_sup_time = df_sup.index[-1]

        if last_df_time - last_sup_time > pd.Timedelta(minutes=10):
            return False

        idx_last_sup = last_sup_time - pd.Timedelta(minutes=15)
        pos_last_sup = df.index.get_loc(idx_last_sup)

        start_pos = pos_last_sup - nb_minutes_before
        end_pos = pos_last_sup
        if start_pos < 0:
            return False

        df_zone = df.iloc[start_pos:end_pos]

        crit_3 = (df_zone["close"] < df_zone["ma"]).sum() == 0
        crit_4 = (df_zone["low"] < df_zone["ma"]).sum() > 0

        if verbose:
            print(
                f"[detecte_casse_ma] "
                f"C1={crit_1} | C3={crit_3} | C4={crit_4}"
            )

        return crit_1 and crit_3 and crit_4, df_sup["ma"].iloc[-1]

    # =========================================================
    # Détection atteinte MA + RSI + closes non figés
    # =========================================================
    def detecte_atteint_ma(
        self,
        df: pd.DataFrame,
        ma_period: int,
        verbose: bool = True
    ) -> bool:

        df = df.iloc[-self.lookback:].copy()

        if len(df) < max(ma_period, 14, 10) + 2:
            return False

        df["ma"] = df["close"].rolling(ma_period).mean()
        df["rsi_5"] = self._compute_rsi(df["close"], 5)
        df["rsi_9"] = self._compute_rsi(df["close"], 9)
        df["rsi_14"] = self._compute_rsi(df["close"], 14)

        last = df.iloc[-1]

        if pd.isna(last["ma"]) or pd.isna(last["rsi_14"]):
            return False

        # -----------------------------
        # C1 : High proche MA
        # -----------------------------
        high_now = last["high"]
        ma_now = last["ma"]

        crit_1 = high_now < ma_now and high_now > 0.995 * ma_now

        # -----------------------------
        # C2 : RSI élevés
        # -----------------------------
        crit_2 = (
            last["rsi_5"] > 80 and
            last["rsi_9"] > 70 and
            last["rsi_14"] > 65
        )

        # -----------------------------
        # C3 : aucun close identique successif (10 dernières minutes)
        # -----------------------------
        df_last_10 = df.iloc[-10:]
        diff = df_last_10["close"].diff().iloc[1:]

        crit_3 = not (diff == 0).any()

        if verbose:
            print(
                f"[detecte_atteint_ma] "
                f"C1(high≈MA)={crit_1} | "
                f"C2(RSI)={crit_2} | "
                f"C3(no_flat_closes_10m)={crit_3}"
            )

        return crit_1 and crit_2 and crit_3
