import sys
import os

# === Gestion du path pour les imports ===
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from downloader import CBitgetDataFetcher
from orders import COrders_Bitget
import CProd


def lire_identifiants(filepath: str) -> dict:
    """
    Récupère les identifiants API (clé, secret, mot de passe) stockés
    sur les 3 premières lignes d’un fichier texte.
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
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Erreur: {e}")
        sys.exit(1)
    return creds


# === Lecture des arguments CLI ===
if len(sys.argv) != 4:
    print("❌ Usage : python main_prod.py <MONTANT> <SYMBOL> <NB_JOURS>")
    print("Exemple : python main_prod.py 100 BNBUSDT 7")
    sys.exit(1)

# 1️⃣ Montant
try:
    montant = int(sys.argv[1])
    if montant <= 0:
        raise ValueError
except ValueError:
    print("❌ Le montant doit être un entier positif.")
    sys.exit(1)

# 2️⃣ Symbole
symbol = sys.argv[2].upper()

# 3️⃣ Nombre de jours
try:
    nb_jours = int(sys.argv[3])
    if nb_jours <= 0:
        raise ValueError
except ValueError:
    print("❌ Le nombre de jours doit être un entier positif.")
    sys.exit(1)

print(f"✅ Arguments reçus : MONTANT = {montant}, SYMBOL = {symbol}, NB_JOURS = {nb_jours}")

# === Lecture des identifiants ===
identifiants = lire_identifiants("../../../../Bitget_jdu.key")
trader = COrders_Bitget.COrders_Bitget(
    identifiants["api_key"],
    identifiants["api_secret"],
    identifiants["password"]
)

fetcher = CBitgetDataFetcher.BitgetDataFetcher()

# === Lancement du runner ===
runner = CProd.CProd(
    symbols=[symbol],             # symbole passé en argument
    days=nb_jours,                # <-- 3e paramètre : nombre de jours
    trader=trader,
    risk_per_trade_pct=montant,
    strategy_name="CStrat_MinMaxTrend",
    fetcher=fetcher,
    interval="1m"
)

runner.prepare_historical_data()
runner.run_backtest()
runner.run_realtime_loop()
