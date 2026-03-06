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


    def get_rsi_5m_history(self, df, period=14, history=15):

        if len(df) < (period * 5 + 10):
            return None

        # closes des bougies 5m terminées
        closes_5m = df[df.index.minute % 5 == 0]["close"].copy()

        last_time = df.index[-1]

        # ajouter la bougie 5m en cours
        if last_time.minute % 5 != 0:
            closes_5m.loc[last_time] = df["close"].iloc[-1]

        rsi_series = self.compute_rsi_series(closes_5m, period)

        if len(rsi_series) < history:
            return rsi_series

        return rsi_series[-history:]


    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or symbol not in DB:
            print(f"{symbol} : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} : dfoneminute vide")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        rsi_hist = self.get_rsi_5m_history(dfoneminute, period=5, history=15)

        if rsi_hist is None or len(rsi_hist) < 10:
            return False

        # condition RSI
        rsi_condition = np.any(rsi_hist[-10:] < 6)

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

        if rsi_condition and price_condition:

            print(
                f"{symbol} SIGNAL : "
                f"RSI5m<6 dans les 10 derniers | "
                f"prix={last_close:.8f} | "
                f"MA(days)={ma_values}"
            )

        return True