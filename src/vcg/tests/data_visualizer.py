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
    data = pd.read_csv(filepath, skipinitialspace=True)

    x = data['Agents']
    plt.plot(x, data["time1"], marker='o', linestyle='-', label="single threaded")
    #plt.plot(x, data["delta1"], marker='o', linestyle='-', label="delta time multithread vs. single threaded")
    plt.plot(x, data["time2"], marker='o', linestyle='-', label="Approximation")
    #plt.plot(x, data["delta2"], marker='o', linestyle='-', label="delta time approximation vs. single threaded")
    plt.title("Time")
    plt.ylabel("Time (s)")
    plt.xlabel("agents")
    #plt.yscale("symlog", linthresh=0.00001)

    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()



