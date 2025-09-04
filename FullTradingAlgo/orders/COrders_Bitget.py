import ccxt
import time

class COrders_Bitget:
    def __init__(self, api_key: str, api_secret: str, password: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = password
        self.positions = []  # Liste des positions ouvertes
        self.client = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })

        try:
            balance = self.client.fetch_balance()
            print("✅ Connexion à Bitget réussie. Solde disponible (USDT):", balance['total'].get('USDT', 'N/A'))
        except Exception as e:
            raise ConnectionError(f"Échec de la connexion à Bitget : {e}")

    # ===== Méthodes utilitaires =====
    def _usdt_to_amount(self, symbol: str, usdt_amount: float, price=None) -> float:
        if price is None:
            ticker = self.client.fetch_ticker(symbol)
            price = ticker['last']
        amount = usdt_amount / price
        return round(amount, 6)

    def convert_symbol_to_usdt(self, symbol: str) -> str:
        """
        Convertit un symbole Binance (ex: 'SHIBUSDC', 'SOLBUSD', 'BTCUSDT')
        en format CCXT avec USDT uniquement : 'BASE/USDT:USDT'
        """
        possible_quotes = ["USDC", "USDT", "BUSD"]
        for quote in possible_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/USDT:USDT"
        return f"{symbol}/USDT:USDT"

    # ===== Gestion du levier =====
    def set_leverage_isolated(self, symbol: str, leverage: int = 1):
        """
        Force le levier et le mode isolated pour le symbole donné.
        """
        symbol_ccxt = self.convert_symbol_to_usdt(symbol)
        try:
            # Définir le mode isolated (toujours) et le levier
            self.client.set_margin_mode('isolated', symbol_ccxt)
            self.client.set_leverage(leverage, symbol_ccxt, params={"marginMode": "isolated"})
            print(f"⚡ Levier défini à {leverage}x en isolated pour {symbol_ccxt}")
        except Exception as e:
            print(f"❌ Impossible de définir le levier pour {symbol_ccxt} : {e}")

    # ===== Passer un ordre =====
    def open_position(self, symbol: str, side: str, usdt_amount: float, price=None):
        """
        Ouvre une position LONG ou SHORT avec Bitget en isolated et levier 1.
        """
        side_map = {
            "BUY_LONG": {"side": "buy", "holdSide": "long"},
            "SELL_SHORT": {"side": "sell", "holdSide": "short"},
        }

        if side not in side_map:
            raise ValueError(f"Type d'ordre non supporté : {side}")

        order_type = "market" if price is None else "limit"
        symbol_ccxt = self.convert_symbol_to_usdt(symbol)

        # Conversion en quantité (base asset)
        amount = self._usdt_to_amount(symbol_ccxt, usdt_amount, price)

        params = {
            "reduceOnly": False,
            "marginMode": "isolated",
            "holdSide": side_map[side]["holdSide"],  # long ou short
        }

        # 🔹 Forcer levier et mode isolated avant l'ordre
        self.set_leverage_isolated(symbol, leverage=1)

        try:
            order = self.client.create_order(
                symbol=symbol_ccxt,
                type=order_type,
                side=side_map[side]["side"],  # buy ou sell
                amount=amount,
                price=price if price else None,
                params=params,
            )
            print(f"✅ Ordre placé: {order['id']} ({side} sur {symbol_ccxt}, levier=1)")
            return order
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi de l'ordre {side} sur {symbol} : {e}")
            return None

    def close_position(self, symbol: str, side: str, price=None):
        """
        Ferme complètement une position LONG ou SHORT.
        """
        # Mapper les actions de clôture
        side_map = {
            "SELL_LONG": {"side": "sell", "holdSide": "long"},
            "BUY_SHORT": {"side": "buy", "holdSide": "short"},
        }

        if side not in side_map:
            raise ValueError(f"Type d'ordre non supporté pour fermeture : {side}")

        symbol_ccxt = self.convert_symbol_to_usdt(symbol)

        # 🔎 Récupérer la position ouverte
        positions = self.client.fetch_positions([symbol_ccxt])
        position = next((p for p in positions if float(p["contracts"]) > 0), None)

        if not position:
            print(f"⚠️ Aucune position ouverte trouvée pour {symbol_ccxt}")
            return None

        # Quantité exacte à fermer
        amount = float(position["contracts"])

        params = {
            "reduceOnly": True,
            "marginMode": "isolated",
            "holdSide": side_map[side]["holdSide"],
        }

        try:
            order = self.client.create_order(
                symbol=symbol_ccxt,
                type="market",
                side=side_map[side]["side"],
                amount=amount,
                price=price if price else None,
                params=params,
            )
            print(f"✅ Position entièrement fermée: {order['id']} ({side} sur {symbol_ccxt})")
            return order
        except Exception as e:
            print(f"❌ Erreur lors de la fermeture {side} sur {symbol} : {e}")
            return None

    # ===== Solde disponible =====
    def get_available_usdc(self):
        try:
            balance = self.client.fetch_balance()
            usdc_balance = balance['free'].get('USDT')  # USDC n'est pas utilisé, c'est USDT
            if usdc_balance is None:
                print("⚠️ Solde USDT non trouvé dans le compte swap.")
            else:
                print(f"💰 Solde disponible (USDT) sur compte futures : {usdc_balance:.2f}")
            return usdc_balance
        except Exception as e:
            print(f"❌ Erreur lors de la récupération du solde USDT : {e}")
            return None

    # ===== Ajout d'un trade =====
    def place_order(self, price: float, side: str, asset: str, timestamp, amount_usdc: float = 0.0, exit_type: str = None):
        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }
        self._process_order(trade)

    def _process_order(self, trade: dict):
        timestamp = trade["timestamp"]
        price = trade["price"]
        side = trade["side"]
        asset = trade["asset"]
        amount_usdt = trade.get("amount_usdc", 0.0)

        if side in ["BUY_LONG", "SELL_SHORT"]:
            l_order = self.open_position(asset, side, amount_usdt)
            if l_order and l_order.get("status") in ["closed", "filled"]:
                self.positions.append({
                    "side": side,
                    "entry_price": price,
                    "usdc": amount_usdt,
                    "timestamp": timestamp,
                    "asset": asset,
                })
        elif side in ["SELL_LONG", "BUY_SHORT"]:
            #if not self.positions:
            #    return
            #entry = self.positions.pop()
            usdc = 0 #entry["usdc"]
            l_order = self.close_position(asset, side, usdc)
            if l_order and l_order.get("status") in ["closed", "filled"]:
                print("✅ Position fermée immédiatement.")
            #else:
                #self.positions.append(entry)
