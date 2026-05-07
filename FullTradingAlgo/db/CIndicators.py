import os
import pandas as pd

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CIndicators:
    """
    Classe contenant des fonctions indicateurs techniques réutilisables
    
    Convention d'arguments:
    - DBOneS: Dict contenant les données d'UN symbole (DB[symbol])
    - dfoneminute: DataFrame avec les données minute (ou None si non requis)
    """

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI COURANT
    # ======================================================
    def compute_rsi_from_weights(self, DBOneS, dfoneminute, period=5):
        """
        Calcule le RSI courant à partir des poids stockés
        
        Args:
            DBOneS: Dict avec données d'un symbole (contient "4h" avec RSI5_WEIGHTS)
            dfoneminute: DataFrame avec le prix courant (colonne "close")
            period: Période RSI (défaut: 5)
        
        Returns:
            float: Valeur du RSI
        """
        if "4h" not in DBOneS or "RSI5_WEIGHTS" not in DBOneS["4h"]:
            return None
        
        weight = DBOneS["4h"]["RSI5_WEIGHTS"]
        new_close = dfoneminute["close"].iloc[-1]
        
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
    def is_lowest_rsi_last_days(self, DBOneS, dfoneminute=None, min_days=2):
        """
        Vérifie si le RSI courant est le plus bas des N derniers jours
        
        Args:
            DBOneS: Dict avec données d'un symbole (contient "4h" avec RSI5)
            dfoneminute: Non utilisé (peut être None)
            min_days: Nombre de jours à vérifier (défaut: 2)
        
        Returns:
            bool: True si RSI courant est le minimum, False sinon
        """
        if "4h" not in DBOneS or "RSI5" not in DBOneS["4h"]:
            return False

        rsi_history = DBOneS["4h"]["RSI5"]

        if rsi_history is None or len(rsi_history) < min_days * 6:
            return False

        last_values = rsi_history[-int(min_days * 6):]
        
        # RSI courant est le dernier élément de l'historique
        rsi_current = last_values[-1]

        return rsi_current <= min(last_values)

    # ======================================================
    # MA100 (minute)
    # ======================================================
    def compute_ma100(self, DBOneS=None, dfoneminute=None):
        """
        Calcule la MA100 sur les données minute
        
        Args:
            DBOneS: Non utilisé (peut être None)
            dfoneminute: DataFrame avec données minute
        
        Returns:
            Series: MA100 pour chaque ligne du DataFrame
        """
        return dfoneminute["close"].rolling(window=100).mean()

    # ======================================================
    # MA DAILY depuis DBOneS
    # ======================================================
    def is_close_near_daily_ma(self, DBOneS, dfoneminute):
        """
        Vérifie si le prix est proche d'une MA daily (10, 20, 50 ou 100)
        Proche = prix entre MA et MA * 1.01
        
        Args:
            DBOneS: Dict avec données d'un symbole (contient "1d" avec "close")
            dfoneminute: DataFrame avec le prix courant (colonne "close")
        
        Returns:
            bool: True si proche d'une MA, False sinon
        """
        if "1d" not in DBOneS or "close" not in DBOneS["1d"]:
            return False

        closes = DBOneS["1d"]["close"]

        if closes is None or len(closes) == 0:
            return False

        last_close = dfoneminute["close"].iloc[-1]
        df = pd.DataFrame({"close": closes})

        periods = [10, 20, 50, 100]

        for period in periods:

            if len(df) < period:
                continue

            ma = df["close"].rolling(window=period).mean().iloc[-1]

            if pd.isna(ma):
                continue

            if ma <= last_close <= ma * 1.01:
                return True

        return False

    # ======================================================
    # TOUCH MA100
    # ======================================================
    def has_touched_ma100(self, DBOneS=None, dfoneminute=None, ma100=None, n_dernieres_minutes=60):
        """
        Vérifie si le prix a touché la MA100 dans les N dernières minutes
        Touché = high >= 0.995 * MA100
        
        Args:
            DBOneS: Non utilisé (peut être None)
            dfoneminute: DataFrame avec données minute
            ma100: Series contenant la MA100 (doit être fournie)
            n_dernieres_minutes: Nombre de dernières minutes à vérifier (défaut: 60)
        
        Returns:
            bool: True si touchée, False sinon
        """
        df = dfoneminute.copy()
        df["ma100"] = ma100

        df_recent = df.tail(n_dernieres_minutes)

        for _, row in df_recent.iterrows():
            if pd.notna(row["ma100"]):
                if row["high"] >= 0.995 * row["ma100"]:
                    return True

        return False

    # ======================================================
    # CHECK: Prix au-dessus de MA (1day) ET MA en hausse
    # ======================================================
    def check_above_ma_and_ma_inc(self, DBOneS, dfoneminute, ma_period=10, timeframe="1d"):
        """
        Vérifie que:
        1. Le prix courant est au-dessus de la MA (1day)
        2. La MA est en hausse entre ses 2 dernières valeurs
        
        Args:
            DBOneS: Dict avec données d'un symbole (contient le timeframe spécifié)
            dfoneminute: DataFrame avec le prix courant
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si prix > MA ET MA en hausse, False sinon
        """
        
        if timeframe not in DBOneS or "close" not in DBOneS[timeframe]:
            return False
        
        closes = DBOneS[timeframe]["close"]
        
        if closes is None or len(closes) < ma_period + 1:
            return False
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean()
        
        ma_last = ma.iloc[-1]
        ma_prev = ma.iloc[-2]
        
        if pd.isna(ma_last) or pd.isna(ma_prev):
            return False
        
        last_close = dfoneminute["close"].iloc[-1]
        
        # Vérifier: prix > MA
        if last_close <= ma_last:
            return False
        
        # Vérifier: MA en hausse
        if ma_last <= ma_prev:
            return False
        
        return True

    # ======================================================
    # CHECK: Prix au-dessus d'une MA donnée
    # ======================================================
    def check_close_above_ma(self, DBOneS, dfoneminute, ma_period=50, timeframe="1d"):
        """
        Vérifie que le prix courant est au-dessus de la MA spécifiée
        
        Args:
            DBOneS: Dict avec données d'un symbole
            dfoneminute: DataFrame avec le prix courant
            ma_period: Période de la moyenne mobile (défaut: 50)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si close > MA, False sinon
        """
        
        if timeframe not in DBOneS or "close" not in DBOneS[timeframe]:
            return False
        
        closes = DBOneS[timeframe]["close"]
        
        if closes is None or len(closes) < ma_period:
            return False
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean().iloc[-1]
        
        if pd.isna(ma):
            return False
        
        last_close = dfoneminute["close"].iloc[-1]
        
        return last_close > ma

    # ======================================================
    # CHECK: MA en hausse (entre 2 dernières valeurs)
    # ======================================================
    def check_ma_increasing(self, DBOneS, dfoneminute=None, ma_period=10, timeframe="1d"):
        """
        Vérifie que la MA est en hausse entre ses 2 dernières valeurs
        
        Args:
            DBOneS: Dict avec données d'un symbole
            dfoneminute: Non utilisé (peut être None)
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si MA en hausse, False sinon
        """
        
        if timeframe not in DBOneS or "close" not in DBOneS[timeframe]:
            return False
        
        closes = DBOneS[timeframe]["close"]
        
        if closes is None or len(closes) < ma_period + 1:
            return False
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean()
        
        ma_last = ma.iloc[-1]
        ma_prev = ma.iloc[-2]
        
        if pd.isna(ma_last) or pd.isna(ma_prev):
            return False
        
        return ma_last > ma_prev

    # ======================================================
    # CHECK: Plusieurs MAs en ordre (10 > 20 > 50 > 100)
    # ======================================================
    def check_ma_alignment(self, DBOneS, dfoneminute, timeframe="1d"):
        """
        Vérifie que les MAs sont alignées (10 > 20 > 50 > 100) et close > MA10
        Utile pour vérifier une tendance haussière
        
        Args:
            DBOneS: Dict avec données d'un symbole
            dfoneminute: DataFrame avec le prix courant
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si alignement correct, False sinon
        """
        
        if timeframe not in DBOneS or "close" not in DBOneS[timeframe]:
            return False
        
        closes = DBOneS[timeframe]["close"]
        
        if closes is None or len(closes) < 100:
            return False
        
        df = pd.DataFrame({"close": closes})
        
        ma10 = df["close"].rolling(window=10).mean().iloc[-1]
        ma20 = df["close"].rolling(window=20).mean().iloc[-1]
        ma50 = df["close"].rolling(window=50).mean().iloc[-1]
        ma100 = df["close"].rolling(window=100).mean().iloc[-1]
        
        if pd.isna(ma10) or pd.isna(ma20) or pd.isna(ma50) or pd.isna(ma100):
            return False
        
        last_close = dfoneminute["close"].iloc[-1]
        
        return last_close > ma10 > ma20 > ma50 > ma100

    # ======================================================
    # CHECK: Distance à une MA (en %)
    # ======================================================
    def get_ma_distance_percent(self, DBOneS, dfoneminute, ma_period=10, timeframe="1d"):
        """
        Retourne la distance (en %) entre le prix courant et la MA
        Distance positive = prix au-dessus
        Distance négative = prix en-dessous
        
        Args:
            DBOneS: Dict avec données d'un symbole
            dfoneminute: DataFrame avec le prix courant
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            float: Distance en % (None si erreur)
        """
        
        if timeframe not in DBOneS or "close" not in DBOneS[timeframe]:
            return None
        
        closes = DBOneS[timeframe]["close"]
        
        if closes is None or len(closes) < ma_period:
            return None
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean().iloc[-1]
        
        if pd.isna(ma):
            return None
        
        last_close = dfoneminute["close"].iloc[-1]
        
        return ((last_close - ma) / ma) * 100

    # ======================================================
    # CHECK: RSI dans une plage
    # ======================================================
    def check_rsi_range(self, DBOneS=None, dfoneminute=None, rsi_value=None, min_rsi=30, max_rsi=70):
        """
        Vérifie que le RSI est dans une plage donnée
        Utile pour survendus (< 30) ou surachetés (> 70)
        
        Args:
            DBOneS: Non utilisé (peut être None)
            dfoneminute: Non utilisé (peut être None)
            rsi_value: Valeur du RSI actuelle
            min_rsi: RSI minimum (défaut: 30)
            max_rsi: RSI maximum (défaut: 70)
        
        Returns:
            bool: True si RSI dans la plage, False sinon
        """
        
        if rsi_value is None:
            return False
        
        return min_rsi <= rsi_value <= max_rsi
