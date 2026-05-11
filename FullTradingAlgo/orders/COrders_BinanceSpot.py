import ccxt
import time


class COrders_BinanceSpot:

    def __init__(self, api_key: str, api_secret: str, password: str = None):

        self.positions = {}

        self.client = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}
        })

        self.client.load_markets()

        try:
            balance = self.client.fetch_balance()
            print("✅ Connexion Binance OK | USDC :", balance["total"].get("USDC", 0))
        except Exception as e:
            raise ConnectionError(f"Connexion Binance échouée : {e}")

    # ===============================
    # UTILITIES
    # ===============================

    def convert_symbol_to_usdc(self, symbol: str):

        quotes = ["USDT", "USDC", "BUSD"]

        for q in quotes:
            if symbol.endswith(q):
                base = symbol[:-len(q)]
                return f"{base}/USDC"

        return f"{symbol}/USDC"

    def _get_price(self, symbol):

        ticker = self.client.fetch_ticker(symbol)
        return ticker["last"]

    def _usdc_to_amount(self, symbol, usdc, price=None):

        if price is None:
            price = self._get_price(symbol)

        amount = usdc / price
        return float(self.client.amount_to_precision(symbol, amount))

    def _check_min_notional(self, symbol, amount, price):

        market = self.client.market(symbol)

        min_notional = None

        if "cost" in market["limits"] and market["limits"]["cost"]:
            min_notional = market["limits"]["cost"]["min"]

        if min_notional:
            if amount * price < min_notional:
                raise ValueError(
                    f"❌ Ordre trop petit {amount*price:.2f}$ < minNotional {min_notional}"
                )

    # ===============================
    # ORDERS
    # ===============================

    def open_position(self, symbol: str, side: str, usdc_amount: float, price=None):

        if side != "BUY_LONG":
            raise ValueError("Spot supporte uniquement BUY_LONG")

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)

        if price is None:
            price = self._get_price(symbol_ccxt)

        amount = self._usdc_to_amount(symbol_ccxt, usdc_amount, price)

        self._check_min_notional(symbol_ccxt, amount, price)

        try:

            order = self.client.create_order(
                symbol=symbol_ccxt,
                type="market",
                side="buy",
                amount=amount
            )

            print(f"✅ BUY {symbol_ccxt} amount={amount}")

            return order

        except Exception as e:

            print("❌ Achat erreur :", e)
            return None

    def close_position(self, symbol: str, side: str, price=None, amount_ratio=1.0, order_type="market"):

        if side != "SELL_LONG":
            raise ValueError("Spot supporte uniquement SELL_LONG")

        if amount_ratio <= 0 or amount_ratio > 1:
            raise ValueError("amount_ratio doit être entre 0 et 1")

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)
        base = symbol_ccxt.split("/")[0]

        balance = self.client.fetch_balance()

        amount = balance["free"].get(base, 0)

        if amount == 0:
            print("⚠️ Aucun asset à vendre")
            return None

        amount = amount * amount_ratio
        amount = float(self.client.amount_to_precision(symbol_ccxt, amount))

        try:

            if order_type == "market":

                order = self.client.create_order(
                    symbol=symbol_ccxt,
                    type="market",
                    side="sell",
                    amount=amount
                )

                print(f"✅ SELL MARKET {symbol_ccxt} amount={amount}")

            elif order_type == "limit":

                if price is None:
                    raise ValueError("Un prix est requis pour un ordre LIMIT")

                price = float(self.client.price_to_precision(symbol_ccxt, price))

                order = self.client.create_order(
                    symbol=symbol_ccxt,
                    type="limit",
                    side="sell",
                    amount=amount,
                    price=price
                )

                print(f"📌 LIMIT SELL {symbol_ccxt} amount={amount} price={price}")

            else:
                raise ValueError("order_type doit être 'market' ou 'limit'")

            return order

        except Exception as e:

            print("❌ Vente erreur :", e)
            return None

    # ===============================
    # BALANCE
    # ===============================

    def get_available_usdc(self):

        balance = self.client.fetch_balance()
        usdc = balance["free"].get("USDC", 0)

        print(f"💰 USDC disponible : {usdc}")
        return usdc

    # ===============================
    # ORDERS MANAGEMENT
    # ===============================

    def has_pending_order(self, symbol: str):

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)

        orders = self.client.fetch_open_orders(symbol_ccxt)

        return len(orders) > 0

    def cancel_all_open_orders(self, symbol: str):

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)

        orders = self.client.fetch_open_orders(symbol_ccxt)

        for o in orders:
            self.client.cancel_order(o["id"], symbol_ccxt)
            print("❎ cancel", o["id"])

    def get_open_limit_orders(self, symbol: str):

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)

        orders = self.client.fetch_open_orders(symbol_ccxt)

        limit_orders = []

        for o in orders:

            if o["type"] == "limit":

                remaining = o["amount"] - o["filled"]

                limit_orders.append({
                    "id": o["id"],
                    "symbol": symbol_ccxt,
                    "side": o["side"],
                    "price": o["price"],
                    "amount": o["amount"],
                    "filled": o["filled"],
                    "remaining": remaining,
                    "timestamp": o["timestamp"]
                })

        return limit_orders

    # ===============================
    # POSITION RECONSTRUCTION
    # ===============================

    def get_position_info(self, symbol):

        symbol_ccxt = self.convert_symbol_to_usdc(symbol)
        base = symbol_ccxt.split("/")[0]

        balance = self.client.fetch_balance()
        qty = balance["total"].get(base, 0)

        if qty == 0:
            return None

        price = self._get_price(symbol_ccxt)

        trades = self.client.fetch_my_trades(symbol_ccxt)

        trades = sorted(trades, key=lambda x: x["timestamp"], reverse=True)

        remaining_needed = qty
        sold_to_offset = 0.0
        cost = 0.0
        fees = 0.0

        for t in trades:

            if remaining_needed <= 0:
                break

            trade_price = t["price"]
            amount = t["amount"]

            fee = 0.0
            fee_asset = None

            if t.get("fee"):
                fee = t["fee"]["cost"]
                fee_asset = t["fee"]["currency"]

            if t["side"] == "sell":

                sold_to_offset += amount
                if fee_asset and fee_asset != base:
                    fees += fee

            else:

                if fee_asset == base:
                    effective_amount = amount - fee
                    fees += fee * trade_price
                else:
                    effective_amount = amount
                    fees += fee

                if sold_to_offset >= effective_amount:
                    sold_to_offset -= effective_amount
                else:
                    contributing = effective_amount - sold_to_offset
                    sold_to_offset = 0.0
                    contributing = min(contributing, remaining_needed)
                    cost += contributing * trade_price
                    remaining_needed -= contributing

        position_qty = qty - remaining_needed

        if position_qty <= 0:
            return None

        avg_entry = cost / position_qty

        value = qty * price

        pnl = value - cost
        roi = (pnl / cost) * 100

        return {
            "symbol": symbol_ccxt,
            "side": "long",
            "quantity": qty,
            "avg_entry_price": avg_entry,
            "current_price": price,
            "position_value": value,
            "cost": cost,
            "fees_paid": fees,
            "pnl": pnl,
            "roi_percent": roi
        }

    def get_all_positions(self, excluded=("USDC", "USDT", "BUSD")):

        balance = self.client.fetch_balance()
        positions = {}

        for asset, qty in balance["total"].items():
            if asset in excluded or qty == 0:
                continue
            symbol = f"{asset}/USDC"
            if symbol not in self.client.markets:
                continue
            try:
                info = self.get_position_info(asset + "USDC")
                if info:
                    positions[symbol] = info
            except Exception as e:
                print(f"⚠️ Impossible de récupérer {symbol} : {e}")

        return positions

    def get_position_count(self, excluded=("USDC", "USDT", "BUSD")):

        balance = self.client.fetch_balance()
        count = 0

        for asset, qty in balance["total"].items():
            if asset in excluded or qty == 0:
                continue
            symbol = f"{asset}/USDC"
            if symbol in self.client.markets:
                count += 1

        return count

    # ===============================
    # BOT INTERFACE
    # ===============================

    def place_order(self, price, side, asset, timestamp, amount_usdc=0, exit_type=None):

        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }

        self._process_order(trade)

    def _process_order(self, trade):

        price = trade["price"]
        side = trade["side"]
        asset = trade["asset"]
        amount = trade["amount_usdc"]

        if side == "BUY_LONG":

            self.open_position(asset, side, amount, price)

        elif side == "SELL_LONG":

            self.close_position(asset, side, price)

        else:

            print("⚠️ Action non supportée en spot :", side)
