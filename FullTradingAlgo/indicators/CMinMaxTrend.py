import pandas as pd
import numpy as np

class CMinMaxTrend:
    def __init__(self, df, kind="max", name="trend", name_init="init_slope",
                 p_init=-1.0, CstValideMinutes=60, name_slope_change=None):
        """
        df   : DataFrame avec index temporel (1 min) + colonnes 'high' et 'low'
        kind : 'max' pour ligne de tendance haute (résistance),
               'min' pour ligne de tendance basse (support)
        name : colonne de la tendance projetée (avec ajustements)
        name_init : colonne de la tendance projetée avec la pente initiale
        p_init : pente initiale (négative pour max, positive pour min)
        CstValideMinutes : délai minimal (en minutes) avant d'ajuster la pente
        name_slope_change : nom de la colonne des points de changement de pente
                            (par défaut = f"{name}_slope_change")
        """
        self.df = df.copy()
        self.kind = kind
        self.name = name
        self.name_init = name_init
        self.p_init = p_init
        self.CstValideMinutes = CstValideMinutes
        self.name_slope_change = name_slope_change or f"{self.name}_slope_change"

        self._compute_full()

    def _compute_full(self):
        df = self.df

        # Choix du prix pivot
        if self.kind == "max":
            prices = df["high"].values
            p_init = self.p_init if self.p_init < 0 else -abs(self.p_init)
            p_ref_index = np.argmax(prices)
        else:
            prices = df["low"].values
            p_init = self.p_init if self.p_init > 0 else abs(self.p_init)
            p_ref_index = np.argmin(prices)

        p_ref_value = prices[p_ref_index]
        t_ref = df.index[p_ref_index]

        # Courbes
        trend = np.full_like(prices, np.nan, dtype=float)
        init_slope = np.full_like(prices, np.nan, dtype=float)
        slope_change_point = np.full_like(prices, np.nan, dtype=float)  # nouvelle colonne

        # Initialisation
        trend[p_ref_index] = p_ref_value
        init_slope[p_ref_index] = p_ref_value
        p = p_init

        slope_changed = False  # drapeau pour arrêter le tracé d'init_slope

        for i in range(p_ref_index + 1, len(prices)):
            dt_minutes = (df.index[i] - t_ref).total_seconds() / 60.0

            # Tant que la pente n'a pas changé → tracer init_slope
            if not slope_changed:
                init_slope[i] = p_ref_value + p_init * dt_minutes

            # courbe "trend" (qui peut s’ajuster)
            val = p_ref_value + p * dt_minutes
            if self.kind == "max":
                if prices[i] > val+ 0.5:  # dépassement
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new <= 0:  # pente descendante valide
                            p = p_new
                            slope_changed = True
                            slope_change_point[i] = prices[i]  # <-- marquer le high
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val
            else:  # kind == "min"
                if prices[i] < val:  # cassure par le bas
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new >= 0:  # pente montante valide
                            p = p_new
                            slope_changed = True
                            slope_change_point[i] = prices[i]  # <-- marquer le low
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val

        # Injection dans le DataFrame
        df[self.name] = trend
        df[self.name_init] = init_slope
        df[self.name_slope_change] = slope_change_point  # colonne configurable
        self.df = df

    def get_df(self):
        return self.df
