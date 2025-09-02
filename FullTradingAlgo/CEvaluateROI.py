import pandas as pd
import matplotlib.pyplot as plt


class CEvaluateROI:
    def __init__(self, initial_usdc=1000.0, trading_fee_rate=0.001):
        self.initial_usdc = initial_usdc
        self.available_usdc = initial_usdc
        self.trading_fee_rate = trading_fee_rate

        self.trades = []           # Liste brute de tous les ordres (entrée + sortie)
        self.positions = {}        # Positions ouvertes {asset: position_dict}
        self.closed_trades = []    # Positions fermées avec pnl, fee et timestamps
        self.latest_prices = {}    # Derniers prix par actif

    def get_available_usdc(self):
        return self.available_usdc

    def place_order(self, price, side, asset, timestamp, amount_usdc=0.0, exit_type=None):
        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }
        self._process_trade(trade)
        self.trades.append(trade)
        self.latest_prices[asset] = price

    def _process_trade(self, trade):
        side = trade["side"]
        asset = trade["asset"]
        price = trade["price"]
        timestamp = trade["timestamp"]
        amount_usdc = trade.get("amount_usdc", 0.0)

        # ------------------------------
        # Ouverture de position
        # ------------------------------
        if side in ["BUY_LONG", "SELL_SHORT"]:
            if asset in self.positions:
                print(f"⚠️ Position déjà ouverte sur {asset}, trade ignoré : {side} à {timestamp}")
                return

            fee = amount_usdc * self.trading_fee_rate
            net_amount = amount_usdc - fee

            if self.available_usdc < amount_usdc:
                print(f"⚠️ Pas assez d'USDC disponible pour ouvrir position sur {asset}")
                return

            self.available_usdc -= amount_usdc  # bloque le montant brut

            self.positions[asset] = {
                "side": side,
                "entry_price": price,
                "usdc": net_amount,
                "timestamp": timestamp,
                "asset": asset
            }

        # ------------------------------
        # Fermeture de position
        # ------------------------------
        elif side in ["SELL_LONG", "BUY_SHORT"]:
            pos = self.positions.get(asset)
            if pos is None:
                print(f"⚠️ Aucune position ouverte sur {asset} pour fermer à {timestamp}")
                return

            entry_price = pos["entry_price"]
            entry_usdc = pos["usdc"]
            entry_side = pos["side"]

            fee = entry_usdc * self.trading_fee_rate  # frais à la sortie

            # Calcul du PNL brut
            if entry_side == "BUY_LONG" and side == "SELL_LONG":
                pnl = entry_usdc * (price / entry_price - 1)
            elif entry_side == "SELL_SHORT" and side == "BUY_SHORT":
                pnl = entry_usdc * (entry_price / price - 1)
            else:
                print(f"⚠️ Incohérence sens entrée/sortie sur {asset} à {timestamp}")
                return

            self.available_usdc += entry_usdc + pnl - fee  # solde après PNL et frais

            # Enregistrement du trade fermé
            self.closed_trades.append({
                "asset": asset,
                "side": entry_side,
                "entry_price": entry_price,
                "exit_price": price,
                "entry_time": pos["timestamp"],
                "exit_time": timestamp,
                "usdc": entry_usdc,
                "pnl": pnl,
                "fee": fee,
                "net_pnl": pnl - fee,  # PNL net pour résumé et graphique
                "duration": (timestamp - pos["timestamp"]).total_seconds()
            })

            del self.positions[asset]

    # ------------------------------
    # PNL et ROI basé uniquement sur les trades fermés
    # ------------------------------
    def get_final_balance_closed_trades(self):
        return self.initial_usdc + sum(t["net_pnl"] for t in self.closed_trades)

    def get_roi_closed_trades(self):
        total_pnl = sum(t["net_pnl"] for t in self.closed_trades)
        return (total_pnl / self.initial_usdc) * 100

    # ------------------------------
    # Graphique capital et PNL net (trades fermés uniquement)
    # ------------------------------
    def plot_combined(self):
        if not self.closed_trades:
            print("⚠️ Aucun trade fermé à afficher")
            return

        df = pd.DataFrame(self.closed_trades).sort_values("exit_time")
        df["cum_pnl"] = df["net_pnl"].cumsum()
        df["capital"] = self.initial_usdc + df["cum_pnl"]

        plt.figure(figsize=(12, 6))
        plt.plot(df["exit_time"], df["cum_pnl"], label="PNL net cumulatif", color="orange")
        plt.plot(df["exit_time"], df["capital"], label="Capital net", color="blue")
        plt.xlabel("Date")
        plt.ylabel("USDC")
        plt.title("Évolution du capital et PNL net cumulatif (trades fermés uniquement)")
        plt.legend()
        plt.grid(True)
        plt.show()

    # ------------------------------
    # Résumé des performances (trades fermés uniquement)
    # ------------------------------
    def print_summary(self):
        total_pnl = sum(t["net_pnl"] for t in self.closed_trades)
        final_balance = self.initial_usdc + total_pnl
        roi = (total_pnl / self.initial_usdc) * 100

        print("📊 Résumé de la performance (trades fermés uniquement) :")
        print("=" * 40)
        print(f"💰 Capital initial : {self.initial_usdc:.2f} USDC")
        print(f"💼 Solde final (trades fermés) : {final_balance:.2f} USDC")
        print(f"📈 PNL total       : {total_pnl:.2f} USDC")
        print(f"📊 ROI             : {roi:.2f} %")
        print("=" * 40)

        long_trades = [t for t in self.closed_trades if t["side"] == "BUY_LONG"]
        short_trades = [t for t in self.closed_trades if t["side"] == "SELL_SHORT"]
        print(f"🔹 Positions LONG  : {len(long_trades)}")
        print(f"🔸 Positions SHORT : {len(short_trades)}")

        wins = sum(1 for t in self.closed_trades if t["pnl"] > 0)
        losses = sum(1 for t in self.closed_trades if t["pnl"] <= 0)
        print(f"✅ Trades gagnants : {wins}")
        print(f"❌ Trades perdants : {losses}")
        print("=" * 40)

        # Détail par actif
        print("\n📊 Détail par actif (trades fermés uniquement)")
        print("=" * 40)
        assets = set(t["asset"] for t in self.closed_trades)
        for asset in sorted(assets):
            asset_trades = [t for t in self.closed_trades if t["asset"] == asset]
            longs = sum(1 for t in asset_trades if t["side"] == "BUY_LONG")
            shorts = sum(1 for t in asset_trades if t["side"] == "SELL_SHORT")
            pnl_asset = sum(t["net_pnl"] for t in asset_trades)
            roi_asset = (pnl_asset / self.initial_usdc) * 100
            wins_asset = sum(1 for t in asset_trades if t["pnl"] > 0)
            losses_asset = sum(1 for t in asset_trades if t["pnl"] <= 0)
            print(f"🔹 {asset}")
            print(f"   LONGs   : {longs}")
            print(f"   SHORTs  : {shorts}")
            print(f"   PNL     : {pnl_asset:.2f} USDC")
            print(f"   ROI     : {roi_asset:.2f} %")
            print(f"   Gagnants: {wins_asset} | Perdants: {losses_asset}")
