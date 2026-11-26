import sys

import matplotlib.pyplot as plt
import pandas as pd


TIMING_COLUMNS = [
    "brute force",
    "branch and bound",
    "fast pivots",
    "parallel pivots",
]


def read_file(filepath):
    df = pd.read_csv(filepath, skipinitialspace=True)
    df.columns = df.columns.str.strip()

    df["bids"] = pd.to_numeric(df["bids"], errors="coerce")

    for col in TIMING_COLUMNS:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.removesuffix("s")
            .replace("skipped", pd.NA)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def main():
    if len(sys.argv) < 2:
        print("Usage: data_visualizer data_file [data_file ...]")
        return

    files = [read_file(filepath) for filepath in sys.argv[1:]]
    combined = pd.concat(files, ignore_index=True)

    averages = combined.groupby("bids")[TIMING_COLUMNS].mean()

    for col in TIMING_COLUMNS:
        plt.plot(averages.index, averages[col], marker="o", label=col)

    plt.title("Average Time")
    plt.ylabel("Time (s)")
    plt.xlabel("Bids")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    main()
