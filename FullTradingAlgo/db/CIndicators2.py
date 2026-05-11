import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CIndicators2:
    """
    Classe contenant les indicateurs techniques réutilisables
    """

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI COURANT
    # ======================================================
    def compute_rsi_from_weights(
        self,
        DBOneS,
        dfoneminute,
        period=5,
        timeframe="4h"
    ):
        """
        Calcule le RSI courant à partir des poids stockés

        Args:
            DBOneS: Dict avec données d'un symbole
            dfoneminute: DataFrame avec le prix courant
            period: Période RSI
            timeframe: Timeframe utilisé ("1h", "4h", "1d", etc.)

        Returns:
            float: Valeur du RSI
        """

        if timeframe not in DBOneS:
            return None

        key_weights = f"RSI{period}_WEIGHTS"

        if key_weights not in DBOneS[timeframe]:
            return None

        weight = DBOneS[timeframe][key_weights]

        if weight is None:
            return None

        required_keys = ["last_close", "avg_gain", "avg_loss"]

        for key in required_keys:
            if key not in weight:
                return None

        if dfoneminute is None or len(dfoneminute) == 0:
            return None

        new_close = dfoneminute["close"].iloc[-1]

        delta = new_close - weight["last_close"]

        gain = max(delta, 0)
        loss = max(-delta, 0)

        avg_gain = (
            (weight["avg_gain"] * (period - 1)) + gain
        ) / period

        avg_loss = (
            (weight["avg_loss"] * (period - 1)) + loss
        ) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return rsi

    # ======================================================
    # RSI MIN + VARIATION PRIX
    # ======================================================
    def analyse_rsi_min_variation(
            self,
            DBOneS,
            dfoneminute,
            symbol,
            period=5,
            timeframe="4h",
            n_last_values=20,
    ):
        """
        Trouve le RSI minimum parmi les N dernières valeurs,
        puis compare le prix associé à ce RSI minimum
        avec le prix courant.

        Affichage compact sur une seule ligne.
        """

        # ======================================================
        # VALIDATIONS
        # ======================================================
        if DBOneS is None:
            return None

        if timeframe not in DBOneS:
            return None

        key_rsi = f"RSI{period}"
        key_close = "close"

        if key_rsi not in DBOneS[timeframe]:
            return None

        if key_close not in DBOneS[timeframe]:
            return None

        rsi_values = DBOneS[timeframe][key_rsi]
        close_values = DBOneS[timeframe][key_close]

        if rsi_values is None or close_values is None:
            return None

        if len(rsi_values) < n_last_values:
            return None

        if len(close_values) < n_last_values:
            return None

        # ======================================================
        # EXTRACTION DERNIERES VALEURS
        # ======================================================
        last_rsi_values = rsi_values[-n_last_values:]
        last_close_values = close_values[-n_last_values:]

        # ======================================================
        # RSI MIN
        # ======================================================
        rsi_min = last_rsi_values.min()

        index_rsi_min = last_rsi_values.argmin()

        price_at_rsi_min = last_close_values.iloc[index_rsi_min]

        # ======================================================
        # PRIX MIN SUR INTERVAL
        # ======================================================
        price_min_interval = min(last_close_values)

        # ======================================================
        # RSI COURANT
        # ======================================================
        rsi_current = self.compute_rsi_from_weights(
            DBOneS=DBOneS,
            dfoneminute=dfoneminute,
            period=period,
            timeframe=timeframe
        )

        if rsi_current is None:
            return None

        # ======================================================
        # PRIX COURANT
        # ======================================================
        current_price = dfoneminute["close"].iloc[-1]

        # ======================================================
        # VARIATIONS
        # ======================================================
        variation_from_rsi_min = (
                                         (
                                                 current_price - price_at_rsi_min
                                         ) / price_at_rsi_min
                                 ) * 100

        variation_from_interval_min = (
                                              (
                                                      current_price - price_min_interval
                                              ) / price_min_interval
                                      ) * 100

        # ======================================================
        # RESULTATS
        # ======================================================
        result = {
            "rsi_min": float(rsi_min),
            "rsi_current": float(rsi_current),

            "price_at_rsi_min": float(price_at_rsi_min),
            "price_min_interval": float(price_min_interval),
            "current_price": float(current_price),

            "variation_from_rsi_min_percent":
                float(variation_from_rsi_min),

            "variation_from_interval_min_percent":
                float(variation_from_interval_min)
        }

        # ======================================================
        # AFFICHAGE COMPACT
        # ======================================================
        if (rsi_current > rsi_min) & (current_price < price_at_rsi_min):
            print(
            f"[{symbol}] "
            f"[{timeframe}] " 
            f"RSI_MIN={rsi_min:.2f} | "
            f"RSI_NOW={rsi_current:.2f} | "
            f"P_RSI_MIN={price_at_rsi_min:.8f} | "
            f"P_MIN={price_min_interval:.8f} | "
            f"P_NOW={current_price:.8f} | "
            f"ΔRSI_MIN={variation_from_rsi_min:.2f}% | "
            f"ΔMIN={variation_from_interval_min:.2f}%"
            )

        return result