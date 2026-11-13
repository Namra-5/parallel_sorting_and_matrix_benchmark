#!/usr/bin/env python3
"""Figures from the benchmark CSVs (matplotlib is an optional dependency).

  python benchmark/plot_results.py            # speedup plots from results/benchmark_results.csv

Only rows with scaling_valid == True (valid runs, workers <= physical cores) are drawn. Wall-time and kernel-time
speedups are written as separate figures, one panel per input size, with the ideal linear speedup as a dashed line.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
COLORS = {"seq": "#4C72B0", "omp": "#DD8452", "thread2": "#55A868", "mpi": "#C44E52"}
LABELS = {"seq": "Sequential", "omp": "OpenMP", "thread2": "Pthreads", "mpi": "MPI"}


def scaling(csv_path: Path, out_dir: Path) -> None:
    df = pd.read_csv(csv_path)
    d = df[df["scaling_valid"] & (df["model"] != "seq")]
    if d.empty:
        sys.exit("no scaling_valid rows to plot (all configurations invalid or oversubscribed)")
    for workload in sorted(d["workload"].unique()):
        for metric, ylabel, fname in (("kernel_speedup_vs_seq", "Speedup vs sequential (kernel time)", "speedup_kernel"),
                                      ("speedup_vs_seq", "Speedup vs sequential (wall time)", "speedup_wall")):
            w = d[d["workload"] == workload]
            sizes = sorted(w["size"].unique())
            fig, axes = plt.subplots(1, len(sizes), figsize=(5 * len(sizes), 4.2), squeeze=False, sharey=True)
            for ax, size in zip(axes[0], sizes):
                s = w[w["size"] == size]
                for model, g in s.groupby("model"):
                    g = g.sort_values("workers")
                    ax.plot(g["workers"], g[metric], marker="o", color=COLORS.get(model), label=LABELS.get(model, model))
                mx = s["workers"].max()
                ax.plot([1, mx], [1, mx], "k--", lw=1, label="ideal")
                ax.set_title(f"{workload}, n = {size}")
                ax.set_xlabel("workers")
                ax.grid(alpha=0.25)
            axes[0][0].set_ylabel(ylabel)
            axes[0][0].legend(frameon=False)
            fig.tight_layout()
            path = out_dir / f"{workload}_{fname}.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            print("wrote", path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(HERE / "results" / "benchmark_results.csv"))
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    out = Path(a.out_dir) if a.out_dir else HERE / "results"
    out.mkdir(exist_ok=True)
    scaling(Path(a.csv), out)


if __name__ == "__main__":
    main()
