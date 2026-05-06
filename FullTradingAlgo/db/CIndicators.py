import os
import pandas as pd

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class CIndicators:
    """
    Classe contenant des fonctions indicateurs techniques réutilisables
    avec les mêmes patterns d'inputs que CTestAboveTrend
    """

    def __init__(self):
        pass

    # ======================================================
    # CALCUL RSI COURANT
    # ======================================================
    def compute_rsi_from_weights(self, weight, new_close, period):
        """
        Calcule le RSI courant à partir des poids stockés
        
        Args:
            weight: Dict contenant "last_close", "avg_gain", "avg_loss"
            new_close: Nouveau prix de clôture
            period: Période RSI
        
        Returns:
            float: Valeur du RSI
        """
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
    def is_lowest_rsi_last_days(self, DB, symbol, rsi_current, min_days=2):
        """
        Vérifie si le RSI courant est le plus bas des N derniers jours
        
        Args:
            DB: Base de données avec historique RSI
            symbol: Symbole du pair
            rsi_current: Valeur RSI courante
            min_days: Nombre de jours à vérifier (défaut: 2)
        
        Returns:
            bool: True si RSI courant est le minimum, False sinon
        """
        if "RSI5" not in DB[symbol]["4h"]:
            return False

        rsi_history = DB[symbol]["4h"]["RSI5"]

        if rsi_history is None or len(rsi_history) < min_days * 6:
            return False

        last_values = rsi_history[-int(min_days * 6):]

        return rsi_current <= min(last_values)

    # ======================================================
    # MA100 (minute)
    # ======================================================
    def compute_ma100(self, dfoneminute):
        """
        Calcule la MA100 sur les données minute
        
        Args:
            dfoneminute: DataFrame avec données minute
        
        Returns:
            Series: MA100 pour chaque ligne du DataFrame
        """
        return dfoneminute["close"].rolling(window=100).mean()

    # ======================================================
    # MA DAILY depuis DB
    # ======================================================
    def is_close_near_daily_ma(self, DB, symbol, last_close):
        """
        Vérifie si le prix est proche d'une MA daily (10, 20, 50 ou 100)
        Proche = prix entre MA et MA * 1.01
        
        Args:
            DB: Base de données avec données daily
            symbol: Symbole du pair
            last_close: Prix de clôture courant
        
        Returns:
            bool: True si proche d'une MA, False sinon
        """
        if "1d" not in DB[symbol]:
            return False

        if "close" not in DB[symbol]["1d"]:
            return False

        closes = DB[symbol]["1d"]["close"]

        if closes is None or len(closes) == 0:
            return False

        df = pd.DataFrame({"close": closes})

        periods = [10, 20, 50, 100]

        for period in periods:

            if len(df) < period:
                continue

            ma = df["close"].rolling(window=period).mean().iloc[-1]

            if pd.isna(ma):
                continue

            if ma <= last_close <= ma * 1.01:
                print(f"{symbol} | INFO : proche MA{period}d")
                return True

        return False

    # ======================================================
    # TOUCH MA100
    # ======================================================
    def has_touched_ma100(self, dfoneminute, ma100, n_dernieres_minutes=60):
        """
        Vérifie si le prix a touché la MA100 dans les N dernières minutes
        Touché = high >= 0.995 * MA100
        
        Args:
            dfoneminute: DataFrame avec données minute
            ma100: Series contenant la MA100
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
    # CHECK: Prix au-dessus de MA10 (1day) ET MA10 en hausse
    # ======================================================
    def check_above_ma_and_ma_inc(self, DB, dfoneminute, symbol, ma_period=10, timeframe="1d"):
        """
        Vérifie que:
        1. Le prix courant est au-dessus de la MA10 (1day)
        2. La MA10 est en hausse entre ses 2 dernières valeurs
        
        Args:
            DB: Base de données avec les données par timeframe
            dfoneminute: DataFrame avec les données minute (contient le prix courant)
            symbol: Symbole du pair
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si prix > MA10 ET MA10 en hausse, False sinon
        """
        
        # Vérifications basiques
        if DB is None or len(DB) == 0:
            print(f"{symbol} | FAIL : DB vide")
            return False
        
        if symbol not in DB:
            print(f"{symbol} | FAIL : symbole absent DB")
            return False
        
        if timeframe not in DB[symbol]:
            print(f"{symbol} | FAIL : pas de données {timeframe}")
            return False
        
        if "close" not in DB[symbol][timeframe]:
            print(f"{symbol} | FAIL : pas de données close {timeframe}")
            return False
        
        # Récupérer les closes du timeframe
        closes = DB[symbol][timeframe]["close"]
        
        if closes is None or len(closes) < ma_period + 1:
            print(f"{symbol} | FAIL : données insuffisantes pour MA{ma_period} ({len(closes) if closes else 0})")
            return False
        
        # Créer DataFrame pour calculer les MA
        df = pd.DataFrame({"close": closes})
        
        # Calculer la MA
        ma = df["close"].rolling(window=ma_period).mean()
        
        # Récupérer les 2 dernières valeurs de MA
        ma_last = ma.iloc[-1]
        ma_prev = ma.iloc[-2]
        
        if pd.isna(ma_last) or pd.isna(ma_prev):
            print(f"{symbol} | FAIL : MA{ma_period} contient NaN")
            return False
        
        # Récupérer le prix courant
        last_close = dfoneminute["close"].iloc[-1]
        
        # Vérifier: prix > MA10
        if last_close <= ma_last:
            print(f"{symbol} | FAIL : close ({last_close:.4f}) <= MA{ma_period} ({ma_last:.4f})")
            return False
        
        # Vérifier: MA10 en hausse
        if ma_last <= ma_prev:
            print(f"{symbol} | FAIL : MA{ma_period} pas en hausse ({ma_prev:.4f} -> {ma_last:.4f})")
            return False
        
        print(f"{symbol} | ✅ check_above_ma_and_ma_inc SUCCESS | close: {last_close:.4f} > MA{ma_period}: {ma_last:.4f} (en hausse)")
        return True

    # ======================================================
    # CHECK: Prix au-dessus d'une MA donnée
    # ======================================================
    def check_close_above_ma(self, DB, dfoneminute, symbol, ma_period=50, timeframe="1d"):
        """
        Vérifie que le prix courant est au-dessus de la MA spécifiée
        
        Args:
            DB: Base de données
            dfoneminute: DataFrame avec les données minute
            symbol: Symbole du pair
            ma_period: Période de la moyenne mobile (défaut: 50)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si close > MA, False sinon
        """
        
        if DB is None or symbol not in DB:
            print(f"{symbol} | FAIL : DB ou symbole invalide")
            return False
        
        if timeframe not in DB[symbol] or "close" not in DB[symbol][timeframe]:
            print(f"{symbol} | FAIL : données {timeframe} manquantes")
            return False
        
        closes = DB[symbol][timeframe]["close"]
        
        if closes is None or len(closes) < ma_period:
            return False
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean().iloc[-1]
        
        if pd.isna(ma):
            return False
        
        last_close = dfoneminute["close"].iloc[-1]
        
        result = last_close > ma
        print(f"{symbol} | close_above_ma{ma_period}: {last_close:.4f} {'>' if result else '<='} {ma:.4f} = {result}")
        
        return result

    # ======================================================
    # CHECK: MA en hausse (entre 2 dernières valeurs)
    # ======================================================
    def check_ma_increasing(self, DB, symbol, ma_period=10, timeframe="1d"):
        """
        Vérifie que la MA est en hausse entre ses 2 dernières valeurs
        
        Args:
            DB: Base de données
            symbol: Symbole du pair
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si MA en hausse, False sinon
        """
        
        if DB is None or symbol not in DB:
            return False
        
        if timeframe not in DB[symbol] or "close" not in DB[symbol][timeframe]:
            return False
        
        closes = DB[symbol][timeframe]["close"]
        
        if closes is None or len(closes) < ma_period + 1:
            return False
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean()
        
        ma_last = ma.iloc[-1]
        ma_prev = ma.iloc[-2]
        
        if pd.isna(ma_last) or pd.isna(ma_prev):
            return False
        
        result = ma_last > ma_prev
        print(f"{symbol} | MA{ma_period} increasing: {ma_prev:.4f} -> {ma_last:.4f} = {result}")
        
        return result

    # ======================================================
    # CHECK: Plusieurs MAs en ordre (10 > 20 > 50 > 100)
    # ======================================================
    def check_ma_alignment(self, DB, dfoneminute, symbol, timeframe="1d"):
        """
        Vérifie que les MAs sont alignées (10 > 20 > 50 > 100) et close > MA10
        Utile pour vérifier une tendance haussière
        
        Args:
            DB: Base de données
            dfoneminute: DataFrame avec les données minute
            symbol: Symbole du pair
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            bool: True si alignement correct, False sinon
        """
        
        if DB is None or symbol not in DB:
            print(f"{symbol} | FAIL : DB ou symbole invalide")
            return False
        
        if timeframe not in DB[symbol] or "close" not in DB[symbol][timeframe]:
            print(f"{symbol} | FAIL : données {timeframe} manquantes")
            return False
        
        closes = DB[symbol][timeframe]["close"]
        
        if closes is None or len(closes) < 100:
            print(f"{symbol} | FAIL : données insuffisantes (min 100 requis)")
            return False
        
        df = pd.DataFrame({"close": closes})
        
        # Calculer les MAs
        ma10 = df["close"].rolling(window=10).mean().iloc[-1]
        ma20 = df["close"].rolling(window=20).mean().iloc[-1]
        ma50 = df["close"].rolling(window=50).mean().iloc[-1]
        ma100 = df["close"].rolling(window=100).mean().iloc[-1]
        
        if pd.isna(ma10) or pd.isna(ma20) or pd.isna(ma50) or pd.isna(ma100):
            print(f"{symbol} | FAIL : MAs contiennent NaN")
            return False
        
        last_close = dfoneminute["close"].iloc[-1]
        
        # Vérifier l'alignement: close > MA10 > MA20 > MA50 > MA100
        if not (last_close > ma10 > ma20 > ma50 > ma100):
            print(f"{symbol} | FAIL : MAs non alignées")
            print(f"  close: {last_close:.4f}")
            print(f"  MA10: {ma10:.4f}")
            print(f"  MA20: {ma20:.4f}")
            print(f"  MA50: {ma50:.4f}")
            print(f"  MA100: {ma100:.4f}")
            return False
        
        print(f"{symbol} | ✅ MA alignment OK: {last_close:.4f} > {ma10:.4f} > {ma20:.4f} > {ma50:.4f} > {ma100:.4f}")
        return True

    # ======================================================
    # CHECK: Distance à une MA (en %)
    # ======================================================
    def get_ma_distance_percent(self, DB, dfoneminute, symbol, ma_period=10, timeframe="1d"):
        """
        Retourne la distance (en %) entre le prix courant et la MA
        Distance positive = prix au-dessus
        Distance négative = prix en-dessous
        
        Args:
            DB: Base de données
            dfoneminute: DataFrame avec les données minute
            symbol: Symbole du pair
            ma_period: Période de la moyenne mobile (défaut: 10)
            timeframe: Timeframe à utiliser (défaut: "1d")
        
        Returns:
            float: Distance en % (None si erreur)
        """
        
        if DB is None or symbol not in DB:
            return None
        
        if timeframe not in DB[symbol] or "close" not in DB[symbol][timeframe]:
            return None
        
        closes = DB[symbol][timeframe]["close"]
        
        if closes is None or len(closes) < ma_period:
            return None
        
        df = pd.DataFrame({"close": closes})
        ma = df["close"].rolling(window=ma_period).mean().iloc[-1]
        
        if pd.isna(ma):
            return None
        
        last_close = dfoneminute["close"].iloc[-1]
        
        distance = ((last_close - ma) / ma) * 100
        print(f"{symbol} | Distance MA{ma_period}: {distance:+.2f}%")
        
        return distance

    # ======================================================
    # CHECK: RSI dans une plage
    # ======================================================
    def check_rsi_range(self, rsi_value, min_rsi=30, max_rsi=70):
        """
        Vérifie que le RSI est dans une plage donnée
        Utile pour survendus (< 30) ou surachetés (> 70)
        
        Args:
            rsi_value: Valeur du RSI actuelle
            min_rsi: RSI minimum (défaut: 30)
            max_rsi: RSI maximum (défaut: 70)
        
        Returns:
            bool: True si RSI dans la plage, False sinon
        """
        
        result = min_rsi <= rsi_value <= max_rsi
        print(f"RSI: {rsi_value:.2f} in range [{min_rsi}, {max_rsi}] = {result}")
        
        return result
