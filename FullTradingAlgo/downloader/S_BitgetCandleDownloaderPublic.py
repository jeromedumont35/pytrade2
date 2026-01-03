import os
import time
import pickle
import requests
from datetime import datetime, timedelta

# === Table de correspondance des intervalles valides Bitget ===
INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "1w": "1W",
    "1M": "1M"
}


class BitgetCandleDownloaderPublic:
    def __init__(self, interval: str = "1m", save_dir: str = "raw"):
        self.interval = INTERVAL_MAP.get(interval, interval)
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.interval_seconds = self._interval_to_seconds(interval)

    # ---------------------------------------------------------
    def _interval_to_seconds(self, interval: str):
        if interval.endswith("m"):
            return int(interval[:-1]) * 60
        elif interval.endswith("h"):
            return int(interval[:-1]) * 3600
        elif interval.endswith("d"):
            return int(interval[:-1]) * 86400
        else:
            return 60  # fallback par défaut

    # ---------------------------------------------------------
    def _get_filename(self, symbol: str, start_time: datetime, end_time: datetime):
        fmt = "%Y%m%d_%H%M"
        return os.path.join(
            self.save_dir,
            f"{symbol}_{start_time.strftime(fmt)}_{end_time.strftime(fmt)}.raw"
        )

    # ---------------------------------------------------------
    def _get_klines(self, symbol: str, start_time_ms: int, end_time_ms: int, limit: int = 1000):
        """
        Récupère les bougies depuis l’API publique Bitget Futures USDT.
        Docs : https://www.bitget.com/api-doc/contract/market/Get-Candlestick-Data
        """
        url = "https://api.bitget.com/api/v2/spot/market/candles"
        params = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "granularity": self.interval,
            "limit": limit,
            "startTime": start_time_ms,
            "endTime": end_time_ms
        }

        for attempt in range(3):  # jusqu’à 3 tentatives si bug API
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        candles = data["data"]
                        candles.sort(key=lambda x: int(x[0]))  # tri croissant
                        return candles
                    else:
                        print(f"⚠️ Données inattendues pour {symbol}: {data}")
                else:
                    print(f"❌ Erreur API Bitget ({symbol}): {response.status_code} -> {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Erreur réseau Bitget ({symbol}): {e}")
            time.sleep(1)
        return []

    # ---------------------------------------------------------
    def _check_continuity(self, candles):
        """Vérifie s’il y a des trous temporels entre les bougies."""
        if len(candles) < 2:
            return False
        expected_delta = self.interval_seconds * 1000
        for i in range(1, len(candles)):
            diff = int(candles[i][0]) - int(candles[i - 1][0])
            if diff > expected_delta * 1.5:  # marge 50%
                return False
        return True

    # ---------------------------------------------------------
    def download_and_save(self, symbol: str, start_time: datetime, end_time: datetime):
        symbol = symbol.upper()
        filename = self._get_filename(symbol, start_time, end_time)

        if os.path.exists(filename):
            print(f"ℹ️ Le fichier existe déjà : {filename}. Téléchargement ignoré.")
            return

        print(f"\n📥 Téléchargement des bougies {symbol} : {start_time} → {end_time}")
        print(f"📁 Fichier de sauvegarde : {filename}")

        all_candles = []
        limit = 1000
        total_seconds = (end_time - start_time).total_seconds()
        last_percent = 0
        current_time = start_time

        while current_time < end_time:
            start_ms = int(current_time.timestamp() * 1000)
            end_ms = start_ms+1000*60*1000

            for retry in range(3):  # 3 essais si trous détectés
                candles = self._get_klines(symbol, start_ms, end_ms, limit)
                if not candles:
                    print(f"\n⚠️ Aucun retour pour {symbol} ({current_time} → {window_end}), retry {retry+1}/3...")
                    time.sleep(2)
                    continue

                if not self._check_continuity(candles):
                    print(f"⚠️ Données discontinues détectées ({current_time} → {window_end}), retry {retry+1}/3...")
                    time.sleep(1)
                    continue  # retélécharger cette même tranche

                # OK : données continues
                all_candles.extend(candles)
                break
            else:
                print(f"❌ Impossible d’obtenir des données continues pour {symbol} ({current_time} → {window_end}).")

            # Avance au prochain segment
            current_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000.0)

            # Affichage de la progression
            elapsed = (current_time - start_time).total_seconds()
            percent = int((elapsed / total_seconds) * 100)
            if percent != last_percent:
                print(f"   ➤ {symbol} : {percent:3d}% | Bougies: {len(all_candles)} | Jusqu'à: {current_time}", end="\r")
                last_percent = percent

            time.sleep(0.15)

        print()
        if all_candles:
            with open(filename, "wb") as f:
                pickle.dump(all_candles, f)
            print(f"✅ {symbol} : {len(all_candles)} bougies enregistrées ({start_time} → {end_time})")
        else:
            print(f"⚠️ Aucune donnée à enregistrer pour {symbol}")


# === Exemple d'utilisation ===
if __name__ == "__main__":
    symbols = ["SOLUSDT"]
    interval = "1min"
    save_dir = "../raw"

    start_time = datetime(2025, 12, 10, 0, 0)
    end_time = datetime(2025, 12, 23, 13, 0)

    downloader = BitgetCandleDownloaderPublic(interval=interval, save_dir=save_dir)

    for sym in symbols:
        downloader.download_and_save(sym.strip(), start_time, end_time)
