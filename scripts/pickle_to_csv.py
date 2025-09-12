import os
import sys
import argparse
import pickle
import pandas as pd
sys.path.append(os.path.join("..", "FullTradingAlgo"))
from strategies.CStrat_RSI5min30 import CStrat_RSI5min30


def main():
    # Parses arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("file_list", nargs="+", type=str, help="Pickle files")
    args = parser.parse_args()

    try:
        for filename in args.file_list:
            with open(filename, "rb") as f:
                candles = pickle.load(f)    # Load pickle files

            # Converts to pandas
            df = pd.DataFrame(candles, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])

            # Prepare dataframe
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df.set_index("time", inplace=True)
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
            df["moy_l_h_e_c"] = (df["open"] + df["close"] + df["high"] + df["low"]) / 4

            # Apply indicators on dataframe
            strategy = CStrat_RSI5min30()
            strategy.apply_indicators(df, True)

            # Panda to csv
            df.to_csv(f"{os.path.splitext(os.path.basename(filename))[0]}.csv", index=False)
            print(f"{os.path.splitext(os.path.basename(filename))[0]}.csv")
    except OSError as e:
        print(e)
        sys.exit()


if __name__ == "__main__":
    main()
