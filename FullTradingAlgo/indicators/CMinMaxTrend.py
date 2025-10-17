import pandas as pd
import numpy as np

class CMinMaxTrend:
    def __init__(
        self, df, kind="max", name="trend", name_init="init_slope",
        p_init=-0.01, CstValideMinutes=60, name_slope_change=None,
        threshold=0.001
    ):
        """
        df   : DataFrame avec index temporel (1 min) + colonnes 'high' et 'low'
        kind : 'max' pour ligne de tendance haute (résistance),
               'min' pour ligne de tendance basse (support)
        name : colonne de la tendance projetée (avec ajustements)
        name_init : colonne de la tendance projetée avec la pente initiale
        p_init : pente initiale (négative pour max, positive pour min)
        CstValideMinutes : délai minimal (en minutes) avant d'ajuster la pente
        name_slope_change : nom de la colonne des points de changement de pente
        threshold : écart minimal (absolu) entre le prix et la tendance pour
                    considérer qu’il y a "dépassement" ou "cassure"
        """
        self.df = df.copy()
        self.kind = kind
        self.name = name
        self.name_init = name_init
        self.p_init = p_init
        self.CstValideMinutes = CstValideMinutes
        self.threshold = threshold
        self.name_slope_change = name_slope_change or f"{self.name}_slope_change"

        # Colonnes internes
        self.col_slope = f"{self.name}_cur_slope"
        self.col_ref_value = f"{self.name}_ref_value"
        self.col_ref_time = f"{self.name}_ref_time"

        # Mode de calcul : initial ou incrémental
        if all(c in self.df.columns for c in [self.name, self.col_slope, self.col_ref_value, self.col_ref_time]):
            self._compute_last()
        else:
            self._compute_full()

    # ======================
    # CALCUL INITIAL COMPLET
    # ======================
    def _compute_full(self):
        df = self.df
        th = self.threshold

        if self.kind == "max":
            prices = df["high"].values
            p = self.p_init if self.p_init < 0 else -abs(self.p_init)
            p_ref_index = np.argmax(prices)
        else:
            prices = df["low"].values
            p = self.p_init if self.p_init > 0 else abs(self.p_init)
            p_ref_index = np.argmin(prices)

        p_ref_value = prices[p_ref_index]
        t_ref = df.index[p_ref_index]

        trend = np.full_like(prices, np.nan, dtype=float)
        init_slope = np.full_like(prices, np.nan, dtype=float)
        slope_change_point = np.full_like(prices, np.nan, dtype=float)
        cur_slope = np.full_like(prices, np.nan, dtype=float)
        ref_values = np.full_like(prices, np.nan, dtype=float)
        ref_times = np.full(len(prices), np.datetime64('NaT'), dtype='datetime64[ns]')

        trend[p_ref_index] = p_ref_value
        init_slope[p_ref_index] = p_ref_value
        cur_slope[p_ref_index] = p
        ref_values[p_ref_index] = p_ref_value
        ref_times[p_ref_index] = t_ref
        slope_changed = False

        for i in range(p_ref_index + 1, len(prices)):
            dt_minutes = (df.index[i] - t_ref).total_seconds() / 60.0

            if not slope_changed:
                init_slope[i] = p_ref_value + self.p_init * dt_minutes

            val = p_ref_value + p * dt_minutes

            if self.kind == "max":
                if prices[i] > val + th:
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new <= 0:
                            p = p_new
                            slope_changed = True
                            slope_change_point[i] = prices[i]
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val
            else:
                if prices[i] < val - th:
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new >= 0:
                            p = p_new
                            slope_changed = True
                            slope_change_point[i] = prices[i]
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val

            cur_slope[i] = p
            ref_values[i] = p_ref_value
            ref_times[i] = t_ref

        df[self.name] = trend
        df[self.name_init] = init_slope
        df[self.name_slope_change] = slope_change_point
        df[self.col_slope] = cur_slope
        df[self.col_ref_value] = ref_values
        df[self.col_ref_time] = ref_times
        self.df = df

    # ===========================
    # MISE À JOUR DERNIÈRE MINUTE
    # ===========================
    def _compute_last(self):
        df = self.df
        th = self.threshold

        last_idx = df.index[-1]
        kind_col = "high" if self.kind == "max" else "low"
        price = df[kind_col].iloc[-1]

        # Reprendre les états précédents
        p_prev = df[self.col_slope].iloc[-2]
        p_ref_value = df[self.col_ref_value].iloc[-2]
        t_ref = df[self.col_ref_time].iloc[-2]

        # ✅ Correction du bug tz-aware vs tz-naive
        dt_minutes = (
            (pd.Timestamp(last_idx).tz_localize(None) - pd.Timestamp(t_ref).tz_localize(None))
            .total_seconds() / 60.0
        )

        val = p_ref_value + p_prev * dt_minutes

        trend = df[self.name].copy()
        init_slope = df[self.name_init].copy()
        slope_change_point = df[self.name_slope_change].copy()
        cur_slope = df[self.col_slope].copy()
        ref_values = df[self.col_ref_value].copy()
        ref_times = df[self.col_ref_time].copy()

        p = p_prev
        slope_changed = False

        if self.kind == "max":
            if price > val + th and dt_minutes >= self.CstValideMinutes:
                p_new = (price - p_ref_value) / dt_minutes
                if p_new <= 0:
                    p = p_new
                    slope_changed = True
                    slope_change_point.iloc[-1] = price
        else:
            if price < val - th and dt_minutes >= self.CstValideMinutes:
                p_new = (price - p_ref_value) / dt_minutes
                if p_new >= 0:
                    p = p_new
                    slope_changed = True
                    slope_change_point.iloc[-1] = price

        trend.iloc[-1] = p_ref_value + p * dt_minutes
        init_slope.iloc[-1] = p_ref_value + self.p_init * dt_minutes
        cur_slope.iloc[-1] = p
        ref_values.iloc[-1] = p_ref_value
        ref_times.iloc[-1] = t_ref

        df[self.name] = trend
        df[self.name_init] = init_slope
        df[self.name_slope_change] = slope_change_point
        df[self.col_slope] = cur_slope
        df[self.col_ref_value] = ref_values
        df[self.col_ref_time] = ref_times
        self.df = df

    def get_df(self):
        return self.df
