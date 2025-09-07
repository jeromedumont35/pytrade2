import pandas as pd

class CRSICalculator:
    def __init__(self, df, period=14,
                 close_times=[(3,59),(7,59),(11,59),(15,59),(19,59),(23,59)],
                 name="rsi"):
        self.df = df.copy()
        self.period = period
        self.close_times = close_times
        self.name = name

        self._check_and_compute()

    def _check_and_compute(self):
        df = self.df
        gain_col = f'avg_gain_{self.name}'
        loss_col = f'avg_loss_{self.name}'

        # Cas 1 : colonnes manquantes → recalcul complet
        if self.name not in df.columns or gain_col not in df.columns or loss_col not in df.columns:
            self._compute_full()
            return

        # Cas 2 : dernière ligne à compléter (même hors close_time)
        last_row = df.iloc[-1]
        if pd.isna(last_row[gain_col]) or pd.isna(last_row[loss_col]) or pd.isna(last_row[self.name]):
            self._update_last()
            return

        # Cas 3 : tout est complet → rien à faire
        self.df = df

    def _compute_full(self):
        """Recalcul complet du RSI aux close_times + interpolation minute par minute"""
        df = self.df
        period = self.period
        alpha = 1 / period

        # Marquage des close_times
        df['is_custom_close'] = df.index.map(lambda x: (x.hour, x.minute) in self.close_times)
        df_close = df[df['is_custom_close']].copy()

        # Différences entre closes
        df_close['delta'] = df_close['close'].diff()
        df_close['gain'] = df_close['delta'].clip(lower=0)
        df_close['loss'] = -df_close['delta'].clip(upper=0)

        gain_col = f'avg_gain_{self.name}'
        loss_col = f'avg_loss_{self.name}'

        # EMA de Wilder
        df_close[gain_col] = df_close['gain'].ewm(alpha=alpha, min_periods=period).mean()
        df_close[loss_col] = df_close['loss'].ewm(alpha=alpha, min_periods=period).mean()

        # RSI aux close_times
        def compute_rsi(gain, loss):
            if pd.isna(gain) or pd.isna(loss):
                return None
            if loss == 0:
                return 100
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        df_close[self.name] = df_close.apply(
            lambda row: compute_rsi(row[gain_col], row[loss_col]), axis=1
        )

        # Fusion avec le df original
        df = df.merge(df_close[[gain_col, loss_col, self.name]],
                      how="left", left_index=True, right_index=True)

        # --- Interpolation minute par minute ---
        last_idx = None
        next_idx = None
        last_gain = None
        last_loss = None
        last_price = None

        for idx in df.index:
            gain = df.at[idx, gain_col]
            loss = df.at[idx, loss_col]

            if pd.notna(gain) and pd.notna(loss):
                # Point de référence (close_time)
                last_gain = gain
                last_loss = loss
                last_idx = idx
                last_price = df.at[idx, 'close']
                rsi = df.at[idx, self.name]
            elif last_idx is not None:
                # Points intermédiaires
                if next_idx is None or idx >= next_idx:
                    future = df.loc[idx:].dropna(subset=[gain_col])
                    next_idx = future.index[0] if not future.empty else None

                close_cur = df.at[idx, 'close']
                delta = close_cur - last_price
                gain_cur = max(delta, 0)
                loss_cur = max(-delta, 0)

                gain_avg = (1 - alpha) * last_gain + alpha * gain_cur
                loss_avg = (1 - alpha) * last_loss + alpha * loss_cur

                rsi = 100 - (100 / (1 + gain_avg / loss_avg)) if loss_avg != 0 else 100

                df.at[idx, gain_col] = gain_avg
                df.at[idx, loss_col] = loss_avg
                df.at[idx, self.name] = rsi

        self.df = df.drop(columns=['is_custom_close','delta','gain','loss'], errors='ignore')

    def _update_last(self):
        """Met à jour la dernière bougie (même hors close_time)"""
        df = self.df
        period = self.period
        alpha = 1 / period

        gain_col = f'avg_gain_{self.name}'
        loss_col = f'avg_loss_{self.name}'

        # Récupère la dernière ligne qui avait un RSI valide
        prev_row = df.dropna(subset=[gain_col, loss_col, self.name]).iloc[-1]
        last_row = df.iloc[-1]

        delta = last_row['close'] - prev_row['close']
        gain = max(delta, 0)
        loss = max(-delta, 0)

        new_avg_gain = (1 - alpha) * prev_row[gain_col] + alpha * gain
        new_avg_loss = (1 - alpha) * prev_row[loss_col] + alpha * loss

        if new_avg_loss == 0:
            new_rsi = 100
        else:
            rs = new_avg_gain / new_avg_loss
            new_rsi = 100 - (100 / (1 + rs))

        # Mise à jour
        df.at[df.index[-1], gain_col] = new_avg_gain
        df.at[df.index[-1], loss_col] = new_avg_loss
        df.at[df.index[-1], self.name] = new_rsi

        self.df = df

    def get_df(self):
        return self.df
