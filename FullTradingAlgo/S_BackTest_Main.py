import os
import sys
import argparse
import traceback
from matplotlib.transforms import BboxBase
import pandas as pd

import CEvaluateROI
import CInterfaceTrades
import CTradingAlgo
from strategies.CStrat_RSI5min30 import CStrat_RSI5min30


def main():
    # Parses arugments
    parser = argparse.ArgumentParser(description="Backtest.")
    parser.add_argument("file_list", nargs="+", type=str, help="Csv files")
    args = parser.parse_args()

    # Création de l'évaluateur
    evaluator = CEvaluateROI.CEvaluateROI(1000, trading_fee_rate=0.001)

    l_interface_trade = CInterfaceTrades.CInterfaceTrades(evaluator)
    algo = CTradingAlgo.CTradingAlgo(evaluator, risk_per_trade_pct=1, strategy_name="RSI5min30")

    # Load data from input files
    list_data = []
    for filename in args.file_list:
        symbol = os.path.basename(filename).split("_")[0]
        df = pd.read_csv(filename)
        list_data.append((df, symbol))

    # Lancement de l'algo
    algo.run(list_data, execution=False)

    evaluator.print_summary()
    evaluator.plot_combined()


if __name__ == "__main__":
    try:
        main() 
    # Catch critical exceptions
    except FileNotFoundError as e:
        traceback.print_exc()
        print(e)
        # print(f"⚠️ Fichier introuvable : {filename}")
        sys.exit(1)
    except Exception as e:
        traceback.print_exc()
        print(e)
        print("Exception")
        sys.exit(1)
