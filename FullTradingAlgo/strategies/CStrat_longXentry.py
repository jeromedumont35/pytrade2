class CStrat_longXentry:

    def __init__(self, symbol, interface, risk_per_trade):

        self.symbol = symbol
        self.interface = interface
        self.risk_per_trade = risk_per_trade

        self.state = "init"

        self.limit_buy_price = None
        self.limit_sell_price = None

    # ==========================================
    # INDICATORS
    # ==========================================

    def apply_indicators(self, df):

        return df

    def get_main_indicators(self):

        return []

    # ==========================================
    # STATE
    # ==========================================

    def get_symbol_state(self):

        return self.state

    # ==========================================
    # STRATEGY CORE
    # ==========================================

    def apply(self, df):

        if len(df) == 0:
            return ""

        close = df["close"].iloc[-1]

        # ==============================
        # INIT STATE
        # ==============================

        if self.state == "init":

            print("STATE INIT")

            # BUY MARKET
            self.interface.open_position(
                self.symbol,
                "BUY_LONG",
                self.risk_per_trade
            )

            # LIMIT BUY 1% BELOW
            self.limit_buy_price = close * 0.99

            self.interface.open_position(
                self.symbol,
                "BUY_LONG",
                self.risk_per_trade,
                price=self.limit_buy_price
            )

            print("LIMIT BUY placed:", self.limit_buy_price)

            self.state = "buy1_done"

            return ""

        # ==============================
        # BUY1_DONE
        # ==============================

        if self.state == "buy1_done":

            orders = self.interface.get_open_limit_orders(self.symbol)

            limit_present = False

            for o in orders:
                if o["side"] == "buy":
                    limit_present = True
                    break

            # --------------------------
            # LIMIT BUY FILLED
            # --------------------------

            if not limit_present:

                print("LIMIT BUY filled")

                self.limit_sell_price = self.limit_buy_price * 1.003

                if close >= self.limit_sell_price:

                    print("Direct SELL market")

                    self.interface.close_position(
                        self.symbol,
                        "SELL_LONG"
                    )

                    self.state = "exit"
                    return ""

                else:

                    print("LIMIT SELL placed:", self.limit_sell_price)

                    self.interface.close_position(
                        self.symbol,
                        "SELL_LONG",
                        price=self.limit_sell_price,
                        order_type="limit"
                    )

                    self.state = "buy2_done"
                    return ""

            # --------------------------
            # LIMIT BUY STILL PRESENT
            # --------------------------

            pos = self.interface.get_position_info(self.symbol)

            if pos:

                if pos["roi_percent"] >= 1:

                    print("ROI 1% reached -> EXIT")

                    self.interface.close_position(
                        self.symbol,
                        "SELL_LONG"
                    )

                    self.state = "exit"

            return ""

        # ==============================
        # BUY2_DONE
        # ==============================

        if self.state == "buy2_done":

            orders = self.interface.get_open_limit_orders(self.symbol)

            sell_present = False

            for o in orders:
                if o["side"] == "sell":
                    sell_present = True
                    break

            if not sell_present:

                print("LIMIT SELL filled -> EXIT")

                self.state = "exit"

            return ""

        return ""
