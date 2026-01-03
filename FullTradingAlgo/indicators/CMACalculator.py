import pandas as pd

class CMACalculator:
    def __init__(self, df, period=20,
                 close_times=[(3,59),(7,59),(11,59),(15,59),(19,59),(23,59)],
                 name="ma"):
        self.df = df.copy()
        self.period = period
        self.close_times = close_times
        self.name = name

        self._check_and_compute()

    def _check_and_compute(self):
        df = self.df

        # Cas 1 : colonne absente → recalcul complet
        if self.name not in df.columns:
            self._compute_full()
            return

        # Cas 2 : dernière ligne à compléter
        if pd.isna(df.iloc[-1][self.name]):
            self._update_last()
            return

        # Cas 3 : tout est OK
        self.df = df

    def _compute_full(self):
        """Calcul complet de la MA aux close_times + propagation minute par minute"""
        df = self.df
        period = self.period

        # Marquage des close_times
        df['is_custom_close'] = df.index.map(
            lambda x: (x.hour, x.minute) in self.close_times
        )

        # Données closes uniquement
        df_close = df[df['is_custom_close']].copy()

        # MA simple basée sur les closes
        df_close[self.name] = df_close['close'].rolling(
            window=period, min_periods=period
        ).mean()

        # Fusion dans le df principal
        df = df.merge(
            df_close[[self.name]],
            how="left",
            left_index=True,
            right_index=True
        )

        # --- Propagation minute par minute ---
        last_ma = None
        last_idx = None

        for idx in df.index:
            ma_val = df.at[idx, self.name]

            if pd.notna(ma_val):
                last_ma = ma_val
                last_idx = idx
            elif last_idx is not None:
                # Valeur figée entre deux close_times
                df.at[idx, self.name] = last_ma

        self.df = df.drop(columns=['is_custom_close'], errors='ignore')

    def _update_last(self):
        """Recalcule uniquement depuis le dernier close_time"""
        df = self.df
        period = self.period

        # Dernier close_time valide
        mask_close = df.index.map(
            lambda x: (x.hour, x.minute) in self.close_times
        )

        valid_closes = df[mask_close].dropna(subset=[self.name])

        if valid_closes.empty:
            self._compute_full()
            return

        last_close_idx = valid_closes.index[-1]

        # Recalcul MA uniquement sur les closes
        df_close = df[mask_close].copy()
        df_close[self.name] = df_close['close'].rolling(
            window=period, min_periods=period
        ).mean()

        # Mise à jour depuis le dernier close_time
        for idx in df.loc[last_close_idx:].index:
            if idx in df_close.index:
                df.at[idx, self.name] = df_close.at[idx, self.name]
            else:
                df.at[idx, self.name] = df.at[last_close_idx, self.name]

        self.df = df

    def get_df(self):
        return self.df
