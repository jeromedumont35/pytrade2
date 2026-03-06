import numpy as np
import pandas as pd


class CTestRSI5Min_MADays:

    def __init__(self):
        pass


    def compute_rsi_series(self, closes, period):

        closes = closes.values
        deltas = np.diff(closes)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi_values = []

        for i in range(period, len(gains)):

            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return np.array(rsi_values)


    def detect_rsi_recovery_pattern(self, df):

        closes_5m = df[df.index.minute % 5 == 0]["close"].copy()
        lows_5m = df[df.index.minute % 5 == 0]["low"].copy()

        last_time = df.index[-1]

        # ajouter la bougie 5m en cours
        if last_time.minute % 5 != 0:
            closes_5m.loc[last_time] = df["close"].iloc[-1]
            lows_5m.loc[last_time] = df["low"].iloc[-1]

        rsi_series = self.compute_rsi_series(closes_5m, 5)

        if len(rsi_series) < 10:
            return False, None

        rsi_series = pd.Series(
            rsi_series,
            index=closes_5m.index[-len(rsi_series):]
        )

        # recherche RSI < 6
        below6 = rsi_series[rsi_series < 6]

        if len(below6) == 0:
            return False, None

        last_below6_time = below6.index[-1]

        # chercher RSI > 20 après
        after = rsi_series[rsi_series.index > last_below6_time]

        above20 = after[after > 20]

        if len(above20) == 0:
            return False, None

        first_above20_time = above20.index[0]

        # calcul du low minimum entre les deux
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

        # détection pattern RSI
        pattern_ok, min_low = self.detect_rsi_recovery_pattern(dfoneminute)

        if not pattern_ok:
            return False

        # condition prix sous le low
        price_break_condition = last_close < min_low

        # périodes MA
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
