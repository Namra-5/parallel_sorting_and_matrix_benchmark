#!/usr/bin/env python3
"""Figures from the benchmark CSVs (matplotlib is an optional dependency).

  python benchmark/plot_results.py            # figures from results/benchmark_results.csv (+ raw_runs.csv)

Only rows with scaling_valid == True (valid runs, workers <= physical cores) are drawn.

  <workload>_speedup_kernel.png   speedup of the in-program compute time, each model against ITS OWN one-worker run
  <workload>_speedup_wall.png     the same for whole-process time
  <workload>_kernel_time.png      absolute kernel time: every valid repetition as a dot, the median as a marker

Each model is compared with its own one-worker run because the implementations differ (a shared sequential baseline would
mix code quality with parallelism). One panel per input size; the ideal linear speedup is dashed. The subtitle names the
machine when hardware_environment.json is next to the CSV. Colours are the colour-blind-safe Okabe-Ito palette and every
model also has its own marker shape, so the figures survive greyscale printing.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
ORDER = ["seq", "omp", "thread2", "mpi"]
LABELS = {"seq": "Sequential", "omp": "OpenMP", "thread2": "Pthreads", "mpi": "MPI"}
COLORS = {"seq": "#000000", "omp": "#0072B2", "thread2": "#E69F00", "mpi": "#009E73"}   # Okabe-Ito
MARKERS = {"seq": "D", "omp": "o", "thread2": "s", "mpi": "^"}
WORKLOADS = {"matrix": "Matrix multiplication", "mergesort": "Merge sort"}


def size_label(workload: str, size: int) -> str:
    return f"{size}×{size}" if workload == "matrix" else f"{size:,} elements"


def subtitle(csv_path: Path) -> str:
    """'Intel Core i5-7200U, 2 physical cores' from hardware_environment.json, or '' if it is not there."""
    try:
        hw = json.loads((csv_path.parent / "hardware_environment.json").read_text())
        return f"{hw.get('cpu_model') or 'unknown CPU'}, {hw.get('effective_cores')} physical cores"
    except Exception:
        return ""


def models_in(frame: pd.DataFrame, with_seq: bool) -> list:
    return [m for m in ORDER if m in set(frame["model"]) and (with_seq or m != "seq")]


def finish(fig, axes, ylabel: str, title: str, sub: str, path: Path) -> None:
    axes[0][0].set_ylabel(ylabel)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(title + (f"\n{sub}" if sub else ""), fontsize=12, y=1.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def scaling(csv_path: Path, out_dir: Path) -> None:
    df = pd.read_csv(csv_path)
    d = df[df["scaling_valid"] & (df["model"] != "seq")]
    if d.empty:
        sys.exit("no scaling_valid rows to plot (all configurations invalid or oversubscribed)")
    sub = subtitle(csv_path)
    for workload in sorted(d["workload"].unique()):
        for metric, ylabel, fname, what in (
                ("kernel_speedup_vs_1worker", "Speedup vs 1 worker (kernel time)", "speedup_kernel", "kernel time"),
                ("speedup_vs_1worker", "Speedup vs 1 worker (wall time)", "speedup_wall", "wall time")):
            w = d[d["workload"] == workload]
            sizes = sorted(w["size"].unique())
            fig, axes = plt.subplots(1, len(sizes), figsize=(4.6 * len(sizes), 4.2), squeeze=False, sharey=True)
            for ax, size in zip(axes[0], sizes):
                s = w[w["size"] == size]
                top = float(s["workers"].max())
                ax.plot([1, top], [1, top], "k--", lw=1, label="ideal", zorder=1)
                for model in models_in(s, with_seq=False):
                    g = s[s["model"] == model].sort_values("workers")
                    ax.plot(g["workers"], g[metric], marker=MARKERS[model], ms=7, lw=1.8, color=COLORS[model],
                            label=LABELS[model], zorder=3)
                ax.set_xticks(sorted(s["workers"].unique()))
                ax.set_xlim(0.85, top + 0.15)
                ax.set_title(size_label(workload, size), fontsize=11)
                ax.set_xlabel("workers")
                ax.grid(alpha=0.25)
                if metric == "speedup_vs_1worker":
                    ax.set_ylim(0.9, top + 0.1)
            finish(fig, axes, ylabel, f"{WORKLOADS.get(workload, workload)}: speedup of the {what}", sub,
                   out_dir / f"{workload}_{fname}.png")


def times(csv_path: Path, out_dir: Path, raw_path: Path = None) -> None:
    """Absolute kernel time: all valid repetitions as dots (if raw_runs.csv is available), median as a marker."""
    df = pd.read_csv(csv_path)
    d = df[df["scaling_valid"] & df["kernel_median_s"].notna()]
    raw = None
    raw_path = raw_path or csv_path.parent / "raw_runs.csv"
    if raw_path.exists():
        raw = pd.read_csv(raw_path)
        raw = raw[(raw["status"] == "ok") & raw["kernel_s"].notna()]
    elif {"kernel_min_s", "kernel_max_s"} <= set(df.columns):
        print("raw_runs.csv not found: drawing min-max whiskers instead of individual repetitions")
    else:
        print("neither raw_runs.csv nor kernel_min_s/kernel_max_s available: skipping the kernel-time figures")
        return
    sub = subtitle(csv_path)
    for workload in sorted(d["workload"].unique()):
        w = d[d["workload"] == workload]
        sizes = sorted(w["size"].unique())
        fig, axes = plt.subplots(1, len(sizes), figsize=(4.6 * len(sizes), 4.4), squeeze=False)
        for ax, size in zip(axes[0], sizes):
            s = w[w["size"] == size]
            models = models_in(s, with_seq=True)
            step = 0.07
            for i, model in enumerate(models):
                dx = (i - (len(models) - 1) / 2) * step          # small horizontal offset so models do not overlap
                g = s[s["model"] == model].sort_values("workers")
                xs = [x + dx for x in g["workers"]]
                if raw is not None:
                    r = raw[(raw["workload"] == workload) & (raw["model"] == model) & (raw["size"] == size)
                            & raw["workers"].isin(g["workers"])]
                    ax.scatter([x + dx for x in r["workers"]], r["kernel_s"], s=14, color=COLORS[model], alpha=0.35,
                               linewidths=0, zorder=2)
                else:
                    lo = (g["kernel_median_s"] - g["kernel_min_s"]).clip(lower=0)
                    hi = (g["kernel_max_s"] - g["kernel_median_s"]).clip(lower=0)
                    ax.errorbar(xs, g["kernel_median_s"], yerr=[lo, hi], fmt="none", ecolor=COLORS[model], capsize=3,
                                alpha=0.6, zorder=2)
                ax.plot(xs, g["kernel_median_s"], marker=MARKERS[model], ms=7, lw=1.6, color=COLORS[model],
                        label=LABELS[model], zorder=3)
            ax.set_ylim(bottom=0)   # linear axis from zero: a halving then looks like a halving
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax.set_xticks(sorted(s["workers"].unique()))
            ax.set_xlim(0.7, max(s["workers"]) + 0.3)
            ax.set_title(size_label(workload, size), fontsize=11)
            ax.set_xlabel("workers")
            ax.grid(alpha=0.25, which="major")
        note = "dots: individual repetitions; marker: median" if raw is not None else "marker: median; bars: min-max"
        finish(fig, axes, "Kernel time (s)", f"{WORKLOADS.get(workload, workload)}: kernel time ({note})",
               sub, out_dir / f"{workload}_kernel_time.png")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(HERE / "results" / "benchmark_results.csv"))
    ap.add_argument("--raw", default=None, help="raw_runs.csv (default: next to the CSV)")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    out = Path(a.out_dir) if a.out_dir else HERE / "results"
    out.mkdir(exist_ok=True)
    scaling(Path(a.csv), out)
    times(Path(a.csv), out, Path(a.raw) if a.raw else None)


if __name__ == "__main__":
    main()
