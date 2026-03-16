import sys
import time


def lire_identifiants(filepath: str) -> dict:
    """
    Récupère les identifiants API (clé, secret, mot de passe)
    stockés sur les 3 premières lignes d’un fichier texte.
    """

    creds = {"api_key": None, "api_secret": None, "password": None}

    try:

        with open(filepath, "r", encoding="utf-8") as f:
            lignes = f.readlines()

        if len(lignes) < 2:
            raise ValueError("⚠️ Le fichier doit contenir au moins 2 lignes.")

        creds["api_key"] = lignes[0].strip()
        creds["api_secret"] = lignes[1].strip()

        if len(lignes) >= 3:
            creds["password"] = lignes[2].strip()

    except FileNotFoundError:
        print(f"❌ Fichier introuvable : {filepath}")
        sys.exit(1)

    except Exception as e:
        print(f"⚠️ Erreur lecture identifiants : {e}")
        sys.exit(1)

    return creds


# ===============================
# MAIN TEST
# ===============================

if __name__ == "__main__":

    filepath = "../../../Bitget_jdu.key"

    creds = lire_identifiants(filepath)

    API_KEY = creds["api_key"]
    API_SECRET = creds["api_secret"]

    bot = COrders_BinanceSpot(API_KEY, API_SECRET)

    symbol = "BTCUSDT"

    # ===============================
    # BUY MARKET
    # ===============================

    print("\n----- BUY MARKET TEST -----")

    bot.place_order(
        price=None,
        side="BUY_LONG",
        asset=symbol,
        timestamp=time.time(),
        amount_usdc=12
    )

    print("⏳ attente 5 secondes...")
    time.sleep(5)

    # ===============================
    # POSITION INFO
    # ===============================

    print("\n----- POSITION INFO -----")

    pos = bot.get_position_info(symbol)

    if pos:
        print("📊 Position :", pos)
    else:
        print("⚠️ Aucune position")

    # ===============================
    # LIMIT SELL PARTIEL
    # ===============================

    print("\n----- LIMIT SELL 50% -----")

    price = bot._get_price(bot.convert_symbol_to_usdc(symbol))
    limit_price = price * 1.01

    bot.close_position(
        symbol,
        "SELL_LONG",
        price=limit_price,
        amount_ratio=0.5,
        order_type="limit"
    )

    print("⏳ attente 2 secondes...")
    time.sleep(2)

    # ===============================
    # ORDERS OPEN
    # ===============================

    print("\n----- OPEN LIMIT ORDERS -----")

    orders = bot.get_open_limit_orders(symbol)

    if orders:
        for o in orders:
            print(o)
    else:
        print("⚠️ Aucun ordre LIMIT ouvert")

    # ===============================
    # POSITION INFO UPDATE
    # ===============================

    print("\n----- POSITION INFO UPDATE -----")

    pos = bot.get_position_info(symbol)

    if pos:
        print(pos)

    # ===============================
    # CANCEL ORDERS
    # ===============================

    print("\n----- CANCEL OPEN ORDERS -----")

    bot.cancel_all_open_orders(symbol)

    print("⏳ attente 2 secondes...")
    time.sleep(2)

    # ===============================
    # CLOSE POSITION FINAL
    # ===============================

    print("\n----- FINAL CLOSE POSITION -----")

    bot.close_position(
        symbol,
        "SELL_LONG",
        order_type="market"
    )

    print("\n----- TEST TERMINÉ -----")
