class CSupport:
    def __init__(self, DB):
        self.DB = DB

    # ---------------------------------
    # 🔍 Local highs / lows
    # ---------------------------------
    def detect_local_highs(self, df, window=3):
        highs = []
        for i in range(window, len(df) - window):
            h = df["high"].iloc[i]
            if h == max(df["high"].iloc[i-window:i+window+1]):
                highs.append((df.index[i], h))
        return highs

    def detect_local_lows(self, df, window=3):
        lows = []
        for i in range(window, len(df) - window):
            l = df["low"].iloc[i]
            if l == min(df["low"].iloc[i-window:i+window+1]):
                lows.append((df.index[i], l))
        return lows

    # ---------------------------------
    # ⚡ Breakout avec impulsion
    # ---------------------------------
    def is_strong_breakout(self, df, idx, level, atr_period=14, multiplier=1.5):
        if idx < atr_period:
            return False

        candle_range = df["high"].iloc[idx] - df["low"].iloc[idx]
        atr = (df["high"] - df["low"]).rolling(atr_period).mean().iloc[idx]
        close = df["close"].iloc[idx]

        return close > level and candle_range > atr * multiplier

    # ---------------------------------
    # 🔁 Flip résistance → support
    # ---------------------------------
    def detect_flips(self, df):
        highs = self.detect_local_highs(df)
        flips = []

        for t, level in highs:
            idx = df.index.get_loc(t)

            for j in range(idx + 1, len(df)):
                if self.is_strong_breakout(df, j, level):

                    for k in range(j + 1, len(df)):
                        low = df["low"].iloc[k]

                        if abs(low - level) / level < 0.005:
                            flips.append(level)
                            break
                    break

        return flips

    # ---------------------------------
    # 🧠 Filtrer local lows solides
    # ---------------------------------
    def filter_strong_lows(self, lows, tolerance=0.005, min_touches=2):
        strong = []

        for _, lvl in lows:
            touches = sum(
                1 for _, l in lows if abs(l - lvl) / lvl < tolerance
            )

            if touches >= min_touches:
                strong.append(lvl)

        return strong

    # ---------------------------------
    # 🔗 Clustering des niveaux
    # ---------------------------------
    def cluster_levels(self, levels, tolerance=0.01):
        clusters = []

        for lvl in sorted(levels):
            found = False

            for c in clusters:
                if abs(lvl - c["mean"]) / c["mean"] < tolerance:
                    c["values"].append(lvl)
                    c["mean"] = sum(c["values"]) / len(c["values"])
                    found = True
                    break

            if not found:
                clusters.append({
                    "mean": lvl,
                    "values": [lvl]
                })

        return clusters

    # ---------------------------------
    # 🧠 Scoring
    # ---------------------------------
    def score_level(self, cluster, flip_levels):
        score = len(cluster["values"])

        for v in cluster["values"]:
            if any(abs(v - f) / f < 0.005 for f in flip_levels):
                score += 3  # bonus flip

        return score

    # ---------------------------------
    # 🚀 Calcul supports pour 1 symbole
    # ---------------------------------
    def compute_symbol_supports(self, symbol):
        data = self.DB[symbol]

        df_1d = data["1d"]
        df_4h = data["4h"]
        df_1h = data["1h"]

        # --- flips ---
        flips = (
            self.detect_flips(df_1d) +
            self.detect_flips(df_4h) +
            self.detect_flips(df_1h)
        )

        # --- local lows ---
        lows = []

        for df in [df_1d, df_4h, df_1h]:
            local_lows = self.detect_local_lows(df)
            strong_lows = self.filter_strong_lows(local_lows)
            lows.extend(strong_lows)

        all_levels = flips + lows

        clusters = self.cluster_levels(all_levels)

        current_price = df_1d["close"].iloc[-1]

        supports = [c for c in clusters if c["mean"] < current_price]

        for c in supports:
            c["score"] = self.score_level(c, flips)

        supports = sorted(
            supports,
            key=lambda x: (current_price - x["mean"], -x["score"])
        )

        return supports

    # ---------------------------------
    # 🌍 Calcul pour tous les symboles
    # ---------------------------------
    def compute_all_supports(self):
        result = {}

        for symbol in self.DB.keys():
            try:
                supports = self.compute_symbol_supports(symbol)
                result[symbol] = supports
            except Exception as e:
                print(f"Erreur sur {symbol}: {e}")

        return result