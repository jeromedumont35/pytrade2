import pandas as pd
import numpy as np

class CMinMaxTrend:
    def __init__(self, df, kind="max", name="trend", p_init=-1.0, CstValideMinutes=60):
        """
        df   : DataFrame avec index temporel (1 min) + colonnes 'high' et 'low'
        kind : 'max' pour ligne de tendance haute (résistance),
               'min' pour ligne de tendance basse (support)
        name : suffixe des colonnes calculées
        p_init : pente initiale (négative pour max, positive pour min)
        CstValideMinutes : délai minimal (en minutes) avant d'ajuster la pente
        """
        self.df = df.copy()
        self.kind = kind
        self.name = name
        self.p_init = p_init
        self.CstValideMinutes = CstValideMinutes

        self._check_and_compute()

    def _check_and_compute(self):
        df = self.df
        col_name = f"{self.kind}_{self.name}"

        if col_name not in df.columns or df[col_name].isna().any():
            self._compute_full()
        else:
            self.df = df

    def _compute_full(self):
        df = self.df

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

        trend = np.full_like(prices, np.nan, dtype=float)
        trend[p_ref_index] = p_ref_value
        p = p_init

        for i in range(p_ref_index + 1, len(prices)):
            dt_minutes = (df.index[i] - t_ref).total_seconds() / 60.0
            val = p_ref_value + p * dt_minutes

            if self.kind == "max":
                if prices[i] > val:  # dépassement
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new <= 0:  # pente descendante valide
                            p = p_new
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val

            else:  # kind == "min"
                if prices[i] < val:  # cassure par le bas
                    if dt_minutes >= self.CstValideMinutes:
                        p_new = (prices[i] - p_ref_value) / dt_minutes
                        if p_new >= 0:  # pente montante valide
                            p = p_new
                    trend[i] = p_ref_value + p * dt_minutes
                else:
                    trend[i] = val

        col_name = f"{self.kind}_{self.name}"
        df[col_name] = trend
        self.df = df

    def get_df(self):
        return self.df
