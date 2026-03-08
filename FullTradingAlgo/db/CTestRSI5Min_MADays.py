import numpy as np
import pandas as pd


class CTestRSI5Min_MADays:

    def __init__(self):
        pass


    def compute_rsi_series(self, closes, period):

        delta = closes.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        alpha = 1 / period

        avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.dropna()


    def detect_rsi_recovery_pattern(self, df):

        # -----------------------------
        # construction vraies bougies 5m
        # -----------------------------
        df_5m = df.resample("5T").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        })

        df_5m = df_5m.dropna()

        # -----------------------------
        # ajout bougie 5m courante
        # -----------------------------
        last_time = df.index[-1]
        current_bucket = last_time.floor("5T")

        df_current = df[df.index >= current_bucket]

        if len(df_current) > 0:

            open_ = df_current["open"].iloc[0]
            high_ = df_current["high"].max()
            low_ = df_current["low"].min()
            close_ = df_current["close"].iloc[-1]

            df_5m.loc[current_bucket] = [open_, high_, low_, close_]

        closes_5m = df_5m["close"]
        lows_5m = df_5m["low"]

        # -----------------------------
        # calcul RSI
        # -----------------------------
        rsi_series = self.compute_rsi_series(closes_5m, 5)

        if len(rsi_series) < 3:
            return False, None

        # -----------------------------
        # affichage RSI
        # -----------------------------
        last_rsi_complete = rsi_series.iloc[-2]
        current_rsi = rsi_series.iloc[-1]

        print(f"RSI complet précédent : {last_rsi_complete:.2f}")
        print(f"RSI courant (5m en cours) : {current_rsi:.2f}")

        # -----------------------------
        # DETECTION PATTERN CORRIGEE
        # -----------------------------

        rsi_prev = rsi_series.shift(1)

        cross_below6 = (rsi_prev >= 6) & (rsi_series < 6)
        cross_above20 = (rsi_prev <= 20) & (rsi_series > 20)

        below6_times = rsi_series[cross_below6].index

        if len(below6_times) == 0:
            return False, None

        last_below6_time = below6_times[-1]

        after = rsi_series[rsi_series.index > last_below6_time]

        cross_above20_after = after[
            (after.shift(1) <= 20) & (after > 20)
        ]

        if len(cross_above20_after) == 0:
            return False, None

        first_above20_time = cross_above20_after.index[0]

        # -----------------------------
        # calcul du low minimum
        # -----------------------------
        window_lows = lows_5m[
            (lows_5m.index >= last_below6_time) &
            (lows_5m.index <= first_above20_time)
        ]

        if len(window_lows) == 0:
            return False, None

        min_low = window_lows.min()

        return True, min_low


    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or symbol not in DB:
            print(f"{symbol} : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} : dfoneminute vide")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        pattern_ok, min_low = self.detect_rsi_recovery_pattern(dfoneminute)

        if not pattern_ok:
            return False

        price_break_condition = last_close < min_low

        ma_periods = [9, 19, 49]

        daily_closes = DB[symbol]["1d"]["close"].values

        price_condition = False
        ma_values = []

        for p in ma_periods:

            if len(daily_closes) < p:
                continue

            ma = np.mean(daily_closes[-p:])
            ma_values.append(ma)

            if ma <= last_close <= ma * 1.03:
                price_condition = True

        if price_condition and price_break_condition:

            print(
                f"{symbol} SIGNAL : "
                f"RSI<6 puis >20 | "
                f"break low={min_low:.8f} | "
                f"prix={last_close:.8f} | "
                f"MA(days)={ma_values}"
            )

        return True
