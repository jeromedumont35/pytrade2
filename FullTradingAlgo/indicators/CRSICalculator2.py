import pandas as pd

class RSICalculator:
    def __init__(self, df, period=14, close_times=[(3, 59), (7, 59), (11, 59), (15, 59), (19, 59), (23, 59)], name="rsi"):
        self.df = df.copy()
        self.period = period
        self.close_times = close_times  # List of (hour, minute)
        self.name = name
        self._compute_rsi()

    def _compute_rsi(self):
        df = self.df
        period = self.period
        alpha = 1 / period

        # 1. Marquer les timestamps correspondant aux clôtures voulues
        df['is_custom_close'] = df.index.map(
            lambda x: (x.hour, x.minute) in self.close_times
        )

        # 2. Extraire les closes aux bons moments
        df_close = df[df['is_custom_close']].copy()
        df_close['delta'] = df_close['close'].diff()
        df_close['gain'] = df_close['delta'].apply(lambda x: max(x, 0))
        df_close['loss'] = df_close['delta'].apply(lambda x: max(-x, 0))

        # 3. Moyenne EMA
        df_close[f'avg_gain_{self.name}'] = df_close['gain'].ewm(alpha=alpha, min_periods=period).mean()
        df_close[f'avg_loss_{self.name}'] = df_close['loss'].ewm(alpha=alpha, min_periods=period).mean()

        # 4. Calcul du RSI sur ces points
        def compute_rsi(gain, loss):
            if loss == 0:
                return 100
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        df_close[self.name] = df_close.apply(
            lambda row: compute_rsi(row[f'avg_gain_{self.name}'], row[f'avg_loss_{self.name}']), axis=1
        )

        # 5. Fusion avec df original
        df = df.merge(
            df_close[[f'avg_gain_{self.name}', f'avg_loss_{self.name}', self.name]],
            how='left',
            left_index=True,
            right_index=True
        )

        # 6. Interpolation minute par minute
        gain_filled = []
        loss_filled = []
        rsi_filled = []

        last_idx = None
        next_idx = None
        last_gain = None
        last_loss = None
        last_price = None

        for idx in df.index:
            gain = df.at[idx, f'avg_gain_{self.name}']
            loss = df.at[idx, f'avg_loss_{self.name}']

            if pd.notna(gain) and pd.notna(loss):
                last_gain = gain
                last_loss = loss
                last_idx = idx
                last_price = df.at[idx, 'close']
                rsi = df.at[idx, self.name]
            elif last_idx is not None:
                # Trouver le prochain point avec RSI non-NaN
                if next_idx is None or idx >= next_idx:
                    future = df.loc[idx:].dropna(subset=[f'avg_gain_{self.name}'])
                    if not future.empty:
                        next_idx = future.index[0]
                    else:
                        next_idx = None

                if next_idx is not None:
                    total_steps = (next_idx - last_idx).total_seconds() / 60
                    cur_steps = (idx - last_idx).total_seconds() / 60

                    weight_cur = cur_steps / total_steps
                    weight_last = 1 - weight_cur

                    close_cur = df.at[idx, 'close']
                    delta = close_cur - last_price
                    gain_cur = max(delta, 0)
                    loss_cur = max(-delta, 0)

                    gain_avg = (1 - alpha) * last_gain + alpha * gain_cur
                    loss_avg = (1 - alpha) * last_loss + alpha * loss_cur

                    rsi = 100 - (100 / (1 + gain_avg / loss_avg)) if loss_avg != 0 else 100
                else:
                    rsi = None
            else:
                rsi = None

            gain_filled.append(last_gain if last_gain is not None else None)
            loss_filled.append(last_loss if last_loss is not None else None)
            rsi_filled.append(rsi)

        #df[f'avg_gain_{self.name}'] = gain_filled
        #df[f'avg_loss_{self.name}'] = loss_filled
        df[self.name] = rsi_filled

        self.df = df.drop(columns=['is_custom_close'])

    def get_df(self):
        return self.df
