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


    def compute_reversal_score(
        self,
        min_rsi,
        rsi_peak,
        bars_recovery,
        bars_under6,
        flush_distance
    ):

        score = 0

        # profondeur RSI
        score_depth = max(0, min((6 - min_rsi) / 6, 1))
        score += score_depth * 30

        # force du rebond
        score_rebound = max(0, min((rsi_peak - 20) / 20, 1))
        score += score_rebound * 20

        # vitesse rebond
        score_speed = max(0, 1 - bars_recovery / 10)
        score += score_speed * 15

        # durée capitulation
        score_duration = min(bars_under6 / 6, 1)
        score += score_duration * 10

        # flush final
        score_flush = max(0, min(flush_distance / 0.01, 1))
        score += score_flush * 25

        return round(score)


    def detect_rsi_recovery_pattern(self, df):

        # bougies 5 minutes
        df_5m = df.resample("5min").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        })

        df_5m = df_5m.dropna()

        # bougie 5m en cours
        last_time = df.index[-1]
        current_bucket = last_time.floor("5min")

        df_current = df[df.index >= current_bucket]

        if len(df_current) > 0:

            open_ = df_current["open"].iloc[0]
            high_ = df_current["high"].max()
            low_ = df_current["low"].min()
            close_ = df_current["close"].iloc[-1]

            df_5m.loc[current_bucket] = [open_, high_, low_, close_]

        closes_5m = df_5m["close"]
        lows_5m = df_5m["low"]

        rsi_series = self.compute_rsi_series(closes_5m, 5)

        if len(rsi_series) < 20:
            return False, None, None

        # RSI récents
        recent_rsi = rsi_series.tail(20)

        rsi_prev = recent_rsi.shift(1)

        cross_below6 = (rsi_prev >= 6) & (recent_rsi < 6)

        below6_times = recent_rsi[cross_below6].index

        if len(below6_times) == 0:
            return False, None, None

        last_below6_time = below6_times[-1]

        after = rsi_series[rsi_series.index > last_below6_time]

        cross_above20_after = after[
            (after.shift(1) <= 20) & (after > 20)
        ]

        if len(cross_above20_after) == 0:
            return False, None, None

        first_above20_time = cross_above20_after.index[0]

        # LOW1 = min low entre RSI<6 et maintenant
        window_lows = lows_5m[lows_5m.index >= last_below6_time]

        if len(window_lows) == 0:
            return False, None, None

        low1 = window_lows.min()

        last_close = closes_5m.iloc[-1]

        if last_close >= low1:
            return False, None, None

        # -------------------------
        # Calcul métriques pour score
        # -------------------------

        rsi_window = rsi_series[
            (rsi_series.index >= last_below6_time)
        ]

        min_rsi = rsi_window.min()
        rsi_peak = rsi_window.max()

        bars_recovery = (
            rsi_series.index.get_loc(first_above20_time)
            - rsi_series.index.get_loc(last_below6_time)
        )

        bars_under6 = (rsi_window < 6).sum()

        flush_distance = (low1 - last_close) / low1

        score = self.compute_reversal_score(
            min_rsi,
            rsi_peak,
            bars_recovery,
            bars_under6,
            flush_distance
        )

        return True, low1, score


    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or symbol not in DB:
            print(f"{symbol} : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} : dfoneminute vide")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        pattern_ok, low1, score = self.detect_rsi_recovery_pattern(dfoneminute)

        if not pattern_ok:
            return False

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

        if price_condition:

            print(
                f"{symbol} SIGNAL : "
                f"break low1={low1:.8f} | "
                f"prix={last_close:.8f} | "
                f"score={score}/100 | "
                f"MA(days)={ma_values}"
            )

        return True
