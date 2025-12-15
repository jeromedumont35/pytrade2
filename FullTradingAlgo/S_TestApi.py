from orders import COrders_Bitget

def lire_identifiants(filepath: str) -> dict:
    """
    Récupère les identifiants API (clé, secret, mot de passe) stockés
    sur les 3 premières lignes d’un fichier texte.

    :param filepath: chemin complet + nom du fichier
    :return: dict avec {api_key, api_secret, password}
    """
    creds = {"api_key": None, "api_secret": None, "password": None}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lignes = f.readlines()

        if len(lignes) < 3:
            raise ValueError("⚠️ Le fichier doit contenir au moins 3 lignes.")

        creds["api_key"] = lignes[0].strip()
        creds["api_secret"] = lignes[1].strip()
        creds["password"] = lignes[2].strip()

    except FileNotFoundError:
        print(f"❌ Fichier introuvable: {filepath}")
    except Exception as e:
        print(f"⚠️ Erreur: {e}")

    return creds

identifiants = lire_identifiants("../../Bitget_jdu.key")
print(identifiants)
trader = COrders_Bitget.COrders_Bitget(identifiants["api_key"], identifiants["api_secret"], identifiants["password"])

trader.open_position("XPINUSDT", "SELL_SHORT", 10, price=0.004)

#info = trader.get_position_info("ALPINEUSDT")

if info:
    print("Montant investi :", info["invested"])
    print("Performance actuelle :", info["performance_pct"], "%")