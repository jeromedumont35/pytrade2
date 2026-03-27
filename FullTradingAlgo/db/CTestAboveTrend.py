import os
import pandas as pd

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CTestAboveTrend:

    def __init__(self, n_dernieres_minutes_touche_100=60):
        self.n_dernieres_minutes_touche_100 = n_dernieres_minutes_touche_100

    # ======================================================
    # CALCUL RSI COURANT
    # ======================================================
    def compute_rsi_from_weights(self, weight, new_close, period):
        delta = new_close - weight["last_close"]

        gain = max(delta, 0)
        loss = max(-delta, 0)

        avg_gain = (weight["avg_gain"] * (period - 1) + gain) / period
        avg_loss = (weight["avg_loss"] * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    # ======================================================
    # RSI MIN
    # ======================================================
    def is_lowest_rsi_last_days(self, DB, symbol, rsi_current, min_days=2):

        if "RSI5" not in DB[symbol]["4h"]:
            return False

        rsi_history = DB[symbol]["4h"]["RSI5"]

        if rsi_history is None or len(rsi_history) < min_days * 6:
            return False

        last_values = rsi_history[-int(min_days * 6):]

        return rsi_current <= min(last_values)

    # ======================================================
    # MA100 (minute)
    # ======================================================
    def compute_ma100(self, dfoneminute):
        return dfoneminute["close"].rolling(window=100).mean()

    # ======================================================
    # MA DAILY depuis DB
    # ======================================================
    def is_close_near_daily_ma(self, DB, symbol, last_close):

        if "1d" not in DB[symbol]:
            return False

        if "close" not in DB[symbol]["1d"]:
            return False

        closes = DB[symbol]["1d"]["close"]

        if closes is None or len(closes) == 0:
            return False

        df = pd.DataFrame({"close": closes})

        periods = [10, 20, 50, 100]

        for period in periods:

            if len(df) < period:
                continue

            ma = df["close"].rolling(window=period).mean().iloc[-1]

            if pd.isna(ma):
                continue

            if ma <= last_close <= ma * 1.01:
                print(f"{symbol} | INFO : proche MA{period}d")
                return True

        return False

    # ======================================================
    # TOUCH MA100
    # ======================================================
    def has_touched_ma100(self, dfoneminute, ma100):

        df = dfoneminute.copy()
        df["ma100"] = ma100

        df_recent = df.tail(self.n_dernieres_minutes_touche_100)

        for _, row in df_recent.iterrows():
            if pd.notna(row["ma100"]):
                if row["high"] >= 0.995 * row["ma100"]:
                    return True

        return False

    # ======================================================
    # MAIN
    # ======================================================
    def realiser(self, DB, dfoneminute, symbol):

        if DB is None or len(DB) == 0:
            print(f"{symbol} | FAIL : DB vide")
            return False

        if dfoneminute is None or len(dfoneminute) == 0:
            print(f"{symbol} | FAIL : dfoneminute vide")
            return False

        if symbol not in DB:
            print(f"{symbol} | FAIL : symbole absent DB")
            return False

        if "4h" not in DB[symbol]:
            print(f"{symbol} | FAIL : pas de données 4h")
            return False

        last_close = dfoneminute["close"].iloc[-1]

        key_weights = "RSI5_WEIGHTS"

        if key_weights not in DB[symbol]["4h"]:
            print(f"{symbol} | FAIL : pas de weights RSI")
            return False

        weight = DB[symbol]["4h"][key_weights]

        rsi_current = self.compute_rsi_from_weights(
            weight,
            new_close=last_close,
            period=5
        )

        # ======================================================
        # ETAPE 1 : RSI MIN
        # ======================================================
        if not self.is_lowest_rsi_last_days(DB, symbol, rsi_current, min_days=2):
            print(f"{symbol} | FAIL : RSI pas minimum 2j | RSI actuel: {rsi_current:.2f}")
            return False

        # ======================================================
        # ETAPE 2 : PROCHE MA DAILY (1D)
        # ======================================================
        if not self.is_close_near_daily_ma(DB, symbol, last_close):
            print(f"{symbol} | FAIL : pas proche MA daily")
            return False

        # ======================================================
        # ETAPE 3 : CLOSE < MA100 (1m)
        # ======================================================
        ma100 = self.compute_ma100(dfoneminute)
        last_ma100 = ma100.iloc[-1]

        if pd.isna(last_ma100):
            print(f"{symbol} | FAIL : MA100 NaN")
            return False

        if last_close >= last_ma100:
            print(f"{symbol} | FAIL : close >= MA100")
            return False

        # ======================================================
        # ETAPE 4 : TOUCH MA100
        # ======================================================
        if not self.has_touched_ma100(dfoneminute, ma100):
            print(f"{symbol} | FAIL : pas de touch MA100")
            return False

        # ======================================================
        # SUCCESS
        # ======================================================
        print(
            f"{symbol} | ✅ SUCCESS | "
            f"close: {last_close:.4f} | "
            f"MA100: {last_ma100:.4f} | "
            f"RSI: {rsi_current:.2f}"
        )

        return True