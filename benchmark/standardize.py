#!/usr/bin/env python3
"""raw_runs.csv -> benchmark_results.csv  (one row per workload x size x model x workers x oversubscribed)

Only runs with status == "ok" (exit code 0 AND output identical to the sequential output) are ever aggregated.

  wall time      median over valid repetitions of the whole-process time        -> median_s, mean_s, std_s, min_s, max_s
  kernel time    median over valid repetitions of the in-program compute time   -> kernel_median_s   (may be empty)
  interval       kernel_speedup_vs_1worker_lo / _hi: conservative, distribution-free interval of the kernel speedup against
                 the same model with one worker (order statistics of the repetitions; see speedup_interval)
  range / noise  kernel_min_s, kernel_max_s, kernel_std_s and kernel_cv (= std / mean): large values (say > 0.15) mean the repetitions disagree
                 (thermal throttling, background load) and the configuration should be interpreted with care

Speedup and efficiency, with N = workers:

  speedup_vs_seq          S_N = T_seq / T_N        T_seq = the true sequential binary, SAME workload and SAME size
  efficiency              E_N = S_N / N
  speedup_vs_1worker      S'_N = T_1 / T_N         T_1 = the SAME model with 1 worker, same workload and size
  efficiency_vs_1worker   E'_N = S'_N / N
  kernel_*                the same quantities computed from kernel_median_s (no I/O, no process start-up)

T_seq (and T_1) are never borrowed from another workload or size: they are joined on exactly those keys. A baseline
with no valid run makes every dependent speedup empty rather than wrong.

  status          ok = every repetition valid | PARTIAL = some invalid | INVALID = none valid
  scaling_valid   True only for status != INVALID rows that are NOT oversubscribed (workers <= physical cores).
                  Use this column to select rows for a scaling plot or claim.
"""
from __future__ import annotations

import argparse
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
KEY = ["workload", "model", "size", "workers", "oversubscribed"]
REQUIRED = KEY + ["rep", "wall_s", "status"]
def median_ci_rank(n: int, min_cover: float = 0.90):
    """Largest rank l such that [x_(l), x_(n+1-l)] is a distribution-free confidence interval for the median with exact
    coverage >= min_cover (coverage = 1 - 2 * P(Binomial(n, 1/2) <= l - 1)). Returns (l, coverage) or None if n is too small
    (n = 5 gives the sample range with 93.8%; n = 15 gives [x_(4), x_(12)] with 96.5%)."""
    best = None
    for l in range(1, n // 2 + 1):
        cover = 1 - 2 * sum(comb(n, k) for k in range(l)) / 2 ** n
        if cover >= min_cover:
            best = (l, cover)
    return best


def speedup_interval(base, new):
    """Conservative interval for the ratio median(base) / median(new): each median gets its exact distribution-free
    interval (median_ci_rank) and the ratio bounds are [lo_base / hi_new, hi_base / lo_new]. The ratio of the true medians
    lies inside whenever both medians do, i.e. with probability >= 1 - alpha_base - alpha_new (87.5% for 5 + 5 repetitions,
    93% for 15 + 15), assuming independent repetitions (drift can make the true coverage lower). Deterministic: no random
    numbers are used. Returns (nan, nan) if either side is too small for a 90% median interval."""
    base = np.sort(np.asarray(base, dtype=float))
    new = np.sort(np.asarray(new, dtype=float))
    rb, rn = median_ci_rank(len(base)), median_ci_rank(len(new))
    if rb is None or rn is None:
        return float("nan"), float("nan")
    lb, ln = rb[0], rn[0]
    return float(base[lb - 1] / new[len(new) - ln]), float(base[len(base) - lb] / new[ln - 1])


COLUMNS = KEY + ["n_runs", "n_ok", "n_failed", "n_mismatch", "n_timeout", "n_no_reference",
                 "median_s", "mean_s", "std_s", "min_s", "max_s", "kernel_median_s", "kernel_min_s", "kernel_max_s", "kernel_std_s", "kernel_cv",
                 "seq_median_s", "speedup_vs_seq", "efficiency",
                 "speedup_vs_1worker", "efficiency_vs_1worker",
                 "kernel_speedup_vs_seq", "kernel_efficiency", "kernel_speedup_vs_1worker", "kernel_speedup_vs_1worker_lo",
                 "kernel_speedup_vs_1worker_hi",
                 "status", "scaling_valid"]


def standardize(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"raw_runs.csv is missing required columns: {missing}")
    raw = raw.copy()
    if "kernel_s" not in raw.columns:  # files written by schema_version 1 have no in-program timing
        raw["kernel_s"] = float("nan")
    raw["oversubscribed"] = raw["oversubscribed"].astype(str).str.strip().str.lower().eq("true")
    raw["wall_s"] = pd.to_numeric(raw["wall_s"], errors="coerce")
    raw["kernel_s"] = pd.to_numeric(raw["kernel_s"], errors="coerce")

    ok = raw[raw["status"] == "ok"]
    agg = ok.groupby(KEY).agg(median_s=("wall_s", "median"), mean_s=("wall_s", "mean"), std_s=("wall_s", "std"),
                              min_s=("wall_s", "min"), max_s=("wall_s", "max"), n_ok=("wall_s", "count"),
                              kernel_median_s=("kernel_s", "median"), kernel_mean_s=("kernel_s", "mean"),
                              kernel_std_s=("kernel_s", "std"), kernel_min_s=("kernel_s", "min"),
                              kernel_max_s=("kernel_s", "max"))
    cnt = raw.groupby(KEY)["status"].agg(
        n_runs="count",
        n_failed=lambda s: int((s == "failed").sum()),
        n_mismatch=lambda s: int((s == "mismatch").sum()),
        n_timeout=lambda s: int((s == "timeout").sum()),
        n_no_reference=lambda s: int((s == "no_reference").sum()))
    out = cnt.join(agg, how="left").reset_index()
    out["n_ok"] = out["n_ok"].fillna(0).astype(int)
    out["kernel_cv"] = out["kernel_std_s"] / out["kernel_mean_s"]   # run-to-run noise of the in-program time

    # baseline 1: the sequential binary, joined on workload + size ONLY
    seq = (out[out["model"] == "seq"][["workload", "size", "median_s", "kernel_median_s"]]
           .rename(columns={"median_s": "seq_median_s", "kernel_median_s": "seq_kernel_s"}))
    out = out.merge(seq, on=["workload", "size"], how="left")
    # baseline 2: the SAME model with one worker, joined on workload + size + model
    one = (out[(out["workers"] == 1) & (out["model"] != "seq")][["workload", "size", "model", "median_s",
                                                                  "kernel_median_s"]]
           .rename(columns={"median_s": "one_median_s", "kernel_median_s": "one_kernel_s"}))
    out = out.merge(one, on=["workload", "size", "model"], how="left")

    out["speedup_vs_seq"] = out["seq_median_s"] / out["median_s"]
    out["efficiency"] = out["speedup_vs_seq"] / out["workers"]
    out["speedup_vs_1worker"] = out["one_median_s"] / out["median_s"]
    out["efficiency_vs_1worker"] = out["speedup_vs_1worker"] / out["workers"]
    out["kernel_speedup_vs_seq"] = out["seq_kernel_s"] / out["kernel_median_s"]
    out["kernel_efficiency"] = out["kernel_speedup_vs_seq"] / out["workers"]
    out["kernel_speedup_vs_1worker"] = out["one_kernel_s"] / out["kernel_median_s"]

    # conservative interval of the kernel speedup against the same model with one worker (see speedup_interval)
    samples = {k: v["kernel_s"].dropna().to_numpy() for k, v in ok.groupby(["workload", "model", "size", "workers"])}
    lo, hi = [], []
    for r in out.itertuples():
        a = samples.get((r.workload, r.model, r.size, 1))
        b = samples.get((r.workload, r.model, r.size, r.workers))
        if r.model == "seq" or r.workers == 1 or a is None or b is None:
            lo.append(float("nan"))
            hi.append(float("nan"))
        else:
            l_, h_ = speedup_interval(a, b)
            lo.append(l_)
            hi.append(h_)
    out["kernel_speedup_vs_1worker_lo"] = lo
    out["kernel_speedup_vs_1worker_hi"] = hi

    out["status"] = [("INVALID" if n == 0 else "ok" if n == r else "PARTIAL")
                     for n, r in zip(out["n_ok"], out["n_runs"])]
    out["scaling_valid"] = (out["status"] != "INVALID") & (~out["oversubscribed"])
    return (out[COLUMNS].sort_values(["workload", "size", "model", "workers", "oversubscribed"])
            .round(6).reset_index(drop=True))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=str(HERE / "results" / "raw_runs.csv"))
    ap.add_argument("--out", default=str(HERE / "results" / "benchmark_results.csv"))
    a = ap.parse_args(argv)
    try:
        raw = pd.read_csv(a.raw)
    except FileNotFoundError:
        sys.exit(f"ERROR: {a.raw} not found - run benchmark/run_benchmark.py first.")
    if raw.empty:
        sys.exit(f"ERROR: {a.raw} contains no runs.")
    try:
        out = standardize(raw)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")
    out.to_csv(a.out, index=False)
    n_bad = int((out["status"] == "INVALID").sum())
    n_part = int((out["status"] == "PARTIAL").sum())
    n_over = int((~out["scaling_valid"] & (out["status"] != "INVALID")).sum())
    print(f"wrote {len(out)} configurations -> {a.out}\n"
          f"  INVALID (no valid run): {n_bad} | PARTIAL (some runs invalid): {n_part} | "
          f"oversubscribed, excluded from scaling_valid: {n_over}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
