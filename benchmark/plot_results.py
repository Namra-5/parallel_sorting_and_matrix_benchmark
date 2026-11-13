#!/usr/bin/env python3
"""Figures from the benchmark CSVs (matplotlib is an optional dependency).

  python benchmark/plot_results.py            # scaling plots from results/benchmark_results.csv
  python benchmark/plot_results.py --legacy   # re-draw assets/*.png from legacy_single_run_results.csv

Scaling plots only use rows with scaling_valid == True (valid runs, workers <= physical cores). The legacy charts draw
the unverified MPI bars hatched and grey, with a note in the legend.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COLORS = {"sequential": "#4C72B0", "seq": "#4C72B0", "omp": "#DD8452", "thread2": "#55A868", "mpi": "#C44E52"}
LABELS = {"sequential": "Sequential", "omp": "OpenMP", "thread2": "Pthreads", "mpi": "MPI (4p) - UNVERIFIED"}


def legacy(out_dir: Path) -> None:
    df = pd.read_csv(HERE / "legacy_single_run_results.csv")
    for workload, title, fname in (("matrix", "Matrix Multiplication", "matrix_multiplication_runtime.png"),
                                   ("mergesort", "Merge Sort", "merge_sort_runtime.png")):
        d = df[df["workload"] == workload]
        sizes = list(dict.fromkeys(d["size"]))
        fig, ax = plt.subplots(figsize=(10, 6))
        width = 0.2
        for i, model in enumerate(["sequential", "omp", "thread2", "mpi"]):
            vals = [float(d[(d["size"] == s) & (d["model"] == model)]["time_s"].iloc[0]) for s in sizes]
            unver = model == "mpi"
            ax.bar([x + (i - 1.5) * width for x in range(len(sizes))], vals, width, label=LABELS[model],
                   color="#BBBBBB" if unver else COLORS[model], edgecolor="#555555" if unver else "none",
                   hatch="//" if unver else None)
        ax.set_yscale("log")
        ax.set_xticks(range(len(sizes)))
        ax.set_xticklabels([s.replace("×", "x") for s in sizes])
        ax.set_xlabel("Matrix size" if workload == "matrix" else "Array size")
        ax.set_ylabel("Runtime (seconds, log scale)")
        ax.set_title(f"{title}: legacy single-run times (2025)\nMPI bars are unverified: launch status and output were never checked",
                     fontsize=11, fontweight="bold")
        ax.grid(axis="y", which="both", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(out_dir / fname, dpi=150)
        plt.close(fig)
        print("wrote", out_dir / fname)


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
                    ax.plot(g["workers"], g[metric], marker="o", color=COLORS.get(model), label=LABELS.get(model, model).replace(" (4p) - UNVERIFIED", ""))
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
    ap.add_argument("--legacy", action="store_true")
    ap.add_argument("--csv", default=str(HERE / "results" / "benchmark_results.csv"))
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    if a.legacy:
        out = Path(a.out_dir) if a.out_dir else ROOT / "assets"
        out.mkdir(exist_ok=True)
        legacy(out)
    else:
        out = Path(a.out_dir) if a.out_dir else HERE / "results"
        out.mkdir(exist_ok=True)
        scaling(Path(a.csv), out)


if __name__ == "__main__":
    main()
