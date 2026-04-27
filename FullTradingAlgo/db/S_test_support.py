from CLoadDB import CLoadDB
from CSupport import CSupport
from CPriceDatabase import CPriceDatabase
from CRSIDatabase import CRSIDatabase


def main():

    # ---------------------------------
    # 📦 DB INIT (IMPORTANT)
    # ---------------------------------
    price_db = CPriceDatabase()
    rsi_db = CRSIDatabase()

    loader = CLoadDB(
        available_intervals=["1d", "4h", "1h"],
        price_db=price_db,
        rsi_db=rsi_db,
        rsi_period=5,
        directory="."
    )

    DB = loader.DB

    if not DB:
        print("❌ DB vide")
        return

    print(f"📦 DB chargée ({len(DB)} symbols)")

    # ---------------------------------
    # 🧠 SUPPORTS
    # ---------------------------------
    cs = CSupport(DB)
    supports_all = cs.compute_all_supports()

    print("\n⏳ Supports calculés\n")

    # ---------------------------------
    # 📊 OUTPUT
    # ---------------------------------
    for symbol, supports in supports_all.items():

        if not supports:
            continue

        print(f"\n===== {symbol} =====")

        for s in supports[:5]:
            print(
                f"Support: {round(s.get('mean', 0), 4)} | "
                f"Score: {s.get('score', 0)}"
            )


if __name__ == "__main__":
    main()