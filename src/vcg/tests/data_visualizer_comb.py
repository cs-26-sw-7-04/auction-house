import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import sys
import pandas as pd
def main():
    if len(sys.argv) < 2:
        print("too few arguments")
        print("Usage: data_visualizer data_file")
        return
    filepath = sys.argv[1]
    df = pd.read_csv(filepath, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"": "unused"})
    timing_columns = [
        "brute force",
        "branch and bound",
        "fast pivots",
        "parallel pivots",
    ]

    for col in timing_columns:
        df[col] = (
            df[col].astype(str)
            .str.strip()
            .str.removesuffix("s")
            .replace("skipped", pd.NA)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["bids"] = pd.to_numeric(df["bids"], errors="coerce")

    for col in timing_columns:
        plt.plot(df["bids"], df[col], marker="o", label=col)
    plt.title("Time")
    plt.ylabel("Time (s)")
    plt.xlabel("bids")
    #plt.yscale("symlog", linthresh=0.00001)

    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()



