import time
from pathlib import Path


class CLoadDB:

    def __init__(self, available_intervals, price_db, rsi_db, rsi_period, directory="."):

        self.available_intervals = available_intervals
        self.l_PriceDatabase = price_db
        self.l_RSIDatabase = rsi_db
        self.l_rsiperiod = rsi_period
        self.directory = directory

        # 🔥 SYMBOLS AUTO
        self.symbols = self.get_common_spot_symbols()

        # DB INIT
        self.DB = {}
        for symbol in self.symbols:
            self.DB[symbol] = {}
            for interval in self.available_intervals:
                self.DB[symbol][interval] = {}

        # Chargement initial
        self._initial_load()

        # Map fichiers
        self.file_map = self._map_interval_files()

    # ======================================================
    # SYMBOLS AUTO
    # ======================================================
    def get_common_spot_symbols(self, use_cache=True, cache_file="symbols_cache.txt"):

        if use_cache:
            try:
                with open(cache_file, "r") as f:
                    symbols = f.read().splitlines()
                    if symbols:
                        print(f"📦 Symbols chargés cache ({len(symbols)})")
                        return symbols
            except:
                pass

        try:
            import requests

            r = requests.get(
                "https://api.bitget.com/api/v2/spot/public/symbols",
                timeout=10
            )
            r.raise_for_status()
            data = r.json()

            bitget_symbols = {
                f"{s['baseCoin']}USDT"
                for s in data["data"]
                if s.get("quoteCoin") == "USDT"
            }

            r = requests.get(
                "https://api.binance.com/api/v3/exchangeInfo",
                timeout=10
            )
            r.raise_for_status()
            data = r.json()

            binance_symbols = {
                s["symbol"]
                for s in data["symbols"]
                if s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"
            }

            result = sorted(bitget_symbols.intersection(binance_symbols))

            try:
                with open(cache_file, "w") as f:
                    f.write("\n".join(result))
            except:
                pass

            print(f"🌐 Symbols API chargés ({len(result)})")
            return result

        except Exception as e:
            print(f"⚠ API symbols failed: {e}")

            try:
                with open(cache_file, "r") as f:
                    return f.read().splitlines()
            except:
                return []

    # ======================================================
    # INTERNAL UTILS
    # ======================================================
    def _map_interval_files(self):
        interval_map = {}

        for f in Path(self.directory).glob("*.csv"):
            parts = f.stem.split("_")
            if len(parts) >= 2:
                interval = parts[0]
                interval_map[interval] = f.name

        return interval_map

    def _inject_weights(self, weights_all, symbol, interval):
        try:
            if symbol in weights_all:
                self.DB[symbol][interval][f"RSI{self.l_rsiperiod}_WEIGHTS"] = {
                    "avg_gain": weights_all[symbol]["avg_gain"],
                    "avg_loss": weights_all[symbol]["avg_loss"],
                    "last_close": weights_all[symbol]["last_close"]
                }
        except:
            pass

    # ======================================================
    # INITIAL LOAD
    # ======================================================
    def _initial_load(self):

        for interval in self.available_intervals:

            print(f"⏳ Chargement initial {interval}...")

            price_db_all = self.l_PriceDatabase.load(resolution=interval)
            rsi_db_all = self.l_RSIDatabase.load_rsi(
                resolution=interval,
                rsi_period=self.l_rsiperiod
            )
            weights_all = self.l_RSIDatabase.load_rsi_weights(
                resolution=interval,
                rsi_period=self.l_rsiperiod
            )

            for symbol in self.symbols:

                try:
                    self.DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
                    self.DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
                    self.DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]

                    self.DB[symbol][interval][f"RSI{self.l_rsiperiod}"] = \
                        rsi_db_all[symbol][interval, f"RSI{self.l_rsiperiod}"]

                    self._inject_weights(weights_all, symbol, interval)

                except Exception as e:
                    print(f"⚠ Load error {symbol} {interval}: {e}")

        print(f"✅ DB initialisée avec RSI{self.l_rsiperiod} + WEIGHTS")

    # ======================================================
    # RELOAD INTERVAL
    # ======================================================
    def reload_interval(self, interval):

        print(f"⚡ Reload {interval}")

        price_db_all = self.l_PriceDatabase.load(resolution=interval)
        rsi_db_all = self.l_RSIDatabase.load_rsi(
            resolution=interval,
            rsi_period=self.l_rsiperiod
        )
        weights_all = self.l_RSIDatabase.load_rsi_weights(
            resolution=interval,
            rsi_period=self.l_rsiperiod
        )

        for symbol in self.symbols:

            try:
                if symbol not in self.DB:
                    self.DB[symbol] = {}
                if interval not in self.DB[symbol]:
                    self.DB[symbol][interval] = {}

                self.DB[symbol][interval]["close"] = price_db_all[symbol][interval, "close"]
                self.DB[symbol][interval]["high"]  = price_db_all[symbol][interval, "high"]
                self.DB[symbol][interval]["low"]   = price_db_all[symbol][interval, "low"]

                self.DB[symbol][interval][f"RSI{self.l_rsiperiod}"] = \
                    rsi_db_all[symbol][interval, f"RSI{self.l_rsiperiod}"]

                self._inject_weights(weights_all, symbol, interval)

            except Exception as e:
                print(f"⚠ Reload error {symbol} {interval}: {e}")

        print(f"✅ {interval} reloaded")

    # ======================================================
    # CHECK FILES
    # ======================================================
    def check_and_update_files(self):

        new_file_map = self._map_interval_files()
        changed_intervals = [
            i for i in new_file_map
            if i not in self.file_map or self.file_map[i] != new_file_map[i]
        ]

        if changed_intervals:
            print(f"⚠ Changes detected: {changed_intervals}")
            time.sleep(40)

            for interval in changed_intervals:
                if interval in self.available_intervals:
                    self.reload_interval(interval)

            self.file_map = new_file_map