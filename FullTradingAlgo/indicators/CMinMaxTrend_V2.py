import pandas as pd
import numpy as np

class CMinMaxTrend:
    def __init__(
        self, df, kind="max", name="trend", name_init="init_slope",
        p_init=-0.01, CstValideMinutes=60, name_slope_change=None,
        mode_day=False
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
        mode_day : si True, ancrage initial à 00h00 et dépassements ramenés à 00h00 du jour
        """
        self.df = df.copy()
        self.kind = kind
        self.name = name
        self.name_init = name_init
        self.p_init = p_init
        self.CstValideMinutes = CstValideMinutes
        self.mode_day = mode_day
        self.name_slope_change = name_slope_change or f"{self.name}_slope_change"

        # Colonnes internes
        self.col_slope = f"{self.name}_cur_slope"
        self.col_ref_value = f"{self.name}_ref_value"
        self.col_ref_time = f"{self.name}_ref_time"

        # Mode de calcul
        if all(c in self.df.columns for c in [self.name, self.col_slope, self.col_ref_value, self.col_ref_time]):
            self._compute_last()
        else:
            self._compute_full()

    # ======================
    # CALCUL INITIAL COMPLET
    # ======================
    def _compute_full(self):
        df = self.df

        # === Sélection du point d’ancrage initial
        if self.kind == "max":
            prices = df["high"].values
            p = self.p_init if self.p_init < 0 else -abs(self.p_init)
            i_ref = np.argmax(prices)
        else:
            prices = df["low"].values
            p = self.p_init if self.p_init > 0 else abs(self.p_init)
            i_ref = np.argmin(prices)

        p_ref_value = prices[i_ref]
        t_ref = df.index[i_ref]
        if self.mode_day:
            t_ref = pd.Timestamp(t_ref).normalize()  # 00h00 du jour du max/min

        # === Colonnes
        n = len(prices)
        trend = np.full(n, np.nan)
        init_slope = np.full(n, np.nan)
        slope_change_point = np.full(n, np.nan)
        cur_slope = np.full(n, np.nan)
        ref_values = np.full(n, p_ref_value)
        ref_times = np.full(n, t_ref, dtype='datetime64[ns]')

        trend[i_ref] = p_ref_value
        init_slope[i_ref] = p_ref_value
        cur_slope[i_ref] = p

        # === Calcul dynamique
        for i in range(i_ref + 1, n):
            t_cur = df.index[i]
            dt_minutes = (t_cur - t_ref).total_seconds() / 60.0
            val = p_ref_value + p * dt_minutes

            # Ligne "init"
            init_slope[i] = p_ref_value + self.p_init * dt_minutes

            # --- Tendance descendante (max)
            if self.kind == "max":
                if prices[i] > val and dt_minutes >= self.CstValideMinutes:
                    if self.mode_day:
                        # On utilise le jour du dépassement
                        day = pd.Timestamp(t_cur).normalize()
                        day_data = df.loc[day: day + pd.Timedelta(days=1)]
                        p_day_max = day_data["high"].max()
                        t_day = day
                        dt_day = (t_day - t_ref).total_seconds() / 60.0
                        if dt_day > 0:
                            p_new = (p_day_max - p_ref_value) / dt_day
                            if p_new <= 0:
                                p = p_new
                                slope_change_point[i] = p_day_max
                    else:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new <= 0:
                            p = p_new
                            slope_change_point[i] = prices[i]

                trend[i] = p_ref_value + p * dt_minutes

            # --- Tendance montante (min)
            else:
                if prices[i] < val and dt_minutes >= self.CstValideMinutes:
                    if self.mode_day:
                        day = pd.Timestamp(t_cur).normalize()
                        day_data = df.loc[day: day + pd.Timedelta(days=1)]
                        p_day_min = day_data["low"].min()
                        t_day = day
                        dt_day = (t_day - t_ref).total_seconds() / 60.0
                        if dt_day > 0:
                            p_new = (p_day_min - p_ref_value) / dt_day
                            if p_new >= 0:
                                p = p_new
                                slope_change_point[i] = p_day_min
                    else:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new >= 0:
                            p = p_new
                            slope_change_point[i] = prices[i]

                trend[i] = p_ref_value + p * dt_minutes

            cur_slope[i] = p

        # === Stockage
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
        last_idx = df.index[-1]
        kind_col = "high" if self.kind == "max" else "low"
        price = df[kind_col].iloc[-1]

        # États précédents
        p_prev = df[self.col_slope].iloc[-2]
        p_ref_value = df[self.col_ref_value].iloc[-1]
        t_ref = df[self.col_ref_time].iloc[-1]

        dt_minutes = (
            (pd.Timestamp(last_idx).tz_localize(None) - pd.Timestamp(t_ref).tz_localize(None))
            .total_seconds() / 60.0
        )

        val = p_ref_value + p_prev * dt_minutes
        p = p_prev
        slope_change = np.nan

        if self.kind == "max":
            if price > val and dt_minutes >= self.CstValideMinutes:
                if self.mode_day:
                    day = pd.Timestamp(last_idx).normalize()
                    day_data = df.loc[day: day + pd.Timedelta(days=1)]
                    p_day_max = day_data["high"].max()
                    dt_day = (day - t_ref).total_seconds() / 60.0
                    if dt_day > 0:
                        p_new = (p_day_max - p_ref_value) / dt_day
                        if p_new <= 0:
                            p = p_new
                            slope_change = p_day_max
                else:
                    p_new = (price - p_ref_value) / dt_minutes
                    if p_new <= 0:
                        p = p_new
                        slope_change = price
        else:
            if price < val and dt_minutes >= self.CstValideMinutes:
                if self.mode_day:
                    day = pd.Timestamp(last_idx).normalize()
                    day_data = df.loc[day: day + pd.Timedelta(days=1)]
                    p_day_min = day_data["low"].min()
                    dt_day = (day - t_ref).total_seconds() / 60.0
                    if dt_day > 0:
                        p_new = (p_day_min - p_ref_value) / dt_day
                        if p_new >= 0:
                            p = p_new
                            slope_change = p_day_min
                else:
                    p_new = (price - p_ref_value) / dt_minutes
                    if p_new >= 0:
                        p = p_new
                        slope_change = price

        # Mise à jour
        df.at[last_idx, self.name] = p_ref_value + p * dt_minutes
        df.at[last_idx, self.name_init] = p_ref_value + self.p_init * dt_minutes
        df.at[last_idx, self.name_slope_change] = slope_change
        df.at[last_idx, self.col_slope] = p
        df.at[last_idx, self.col_ref_value] = p_ref_value
        df.at[last_idx, self.col_ref_time] = t_ref
        self.df = df

    def get_df(self):
        return self.df
