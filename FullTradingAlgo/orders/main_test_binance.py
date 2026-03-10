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

    # chemin du fichier
    filepath = "../../../Bitget_jdu.key"

    creds = lire_identifiants(filepath)

    API_KEY = creds["api_key"]
    API_SECRET = creds["api_secret"]

    # création du bot
    bot = COrders_BinanceSpot(API_KEY, API_SECRET)

    symbol = "BTCUSDT"

    print("----- BUY TEST -----")

    bot.place_order(
        price=None,
        side="BUY_LONG",
        asset=symbol,
        timestamp=time.time(),
        amount_usdc=6
    )

    print("⏳ attente 10 secondes...")
    time.sleep(10)

    print("----- SELL TEST -----")

    bot.place_order(
        price=None,
        side="SELL_LONG",
        asset=symbol,
        timestamp=time.time()
    )
