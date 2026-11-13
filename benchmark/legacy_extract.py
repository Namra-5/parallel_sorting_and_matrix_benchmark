#!/usr/bin/env python3
"""Extract the legacy single-run tables from README.md into legacy_single_run_results.csv and flag unreliable rows.

The tables come from the original Test-Script.sh runs (2025). That script discarded mpirun's stdout/stderr, so a failed
launch (OpenMPI: "not enough slots") was timed as if it were a result, and no output was ever compared with the
sequential output. Therefore EVERY legacy MPI row is flagged 'unverified_mpi'. Rows whose speedup over the sequential
time exceeds 1.25 x N (N = 4 processes, 25% slack for cache effects) are additionally flagged
'implausible_superlinear': physically impossible, and consistent with a failed launch (~0.06-0.1 s).
OpenMP/Pthreads core counts were not recorded, so those rows are never flagged.

This script is also a drift guard: the README tables and the committed CSV must agree (see tests).
"""
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ["sequential", "omp", "thread2", "mpi"]
MPI_NP = 4
SECTION = "## Legacy Results"
MARKERS = "¹†‡*"


def parse_time(s: str) -> float:
    s = s.strip().rstrip(MARKERS).strip()
    m = re.fullmatch(r"(?:(\d+)m\s*)?([\d.]+)s", s)
    if not m:
        raise ValueError(f"cannot parse time {s!r}")
    return (int(m.group(1)) * 60 if m.group(1) else 0) + float(m.group(2))


def parse_section(text: str, heading: str) -> list[tuple[str, list[float]]]:
    # restrict to the legacy section first: the same ### headings may appear elsewhere in the README
    text = text.split(SECTION, 1)[1]
    sec = text.split(heading, 1)[1]
    sec = re.split(r"\n###? ", sec, maxsplit=1)[0]
    rows = []
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and re.search(r"\d", cells[0]) and not set(cells[0]) <= set("-: "):
            rows.append((cells[0], [parse_time(c) for c in cells[1:]]))
    return rows


def extract(readme_text: str) -> list[dict]:
    out = []
    for workload, heading in (("matrix", "### Matrix Multiplication"), ("mergesort", "### Merge Sort")):
        for size, times in parse_section(readme_text, heading):
            seq = times[0]
            for model, t in zip(MODELS, times):
                s = seq / t
                flag = ""
                if model == "mpi":
                    flag = "unverified_mpi: launch status and output were never checked"
                    if s > 1.25 * MPI_NP:
                        flag = "implausible_superlinear; " + flag
                out.append({"workload": workload, "size": size, "model": model,
                            "workers": MPI_NP if model == "mpi" else "", "time_s": f"{t:.3f}",
                            "speedup_vs_seq": f"{s:.3f}", "runs": 1,
                            "source": "README.md (single run, `time` real)", "flag": flag})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--readme", default=str(ROOT / "README.md"))
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "legacy_single_run_results.csv"))
    a = ap.parse_args(argv)
    out = extract(Path(a.readme).read_text(encoding="utf-8"))
    with Path(a.out).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    sup = [r for r in out if "implausible" in r["flag"]]
    print(f"{len(out)} rows -> {a.out}; {sum(1 for r in out if r['flag'])} flagged, {len(sup)} physically implausible")
    for r in sup:
        print(f"  {r['workload']} {r['size']} {r['model']}: {r['time_s']}s -> {r['speedup_vs_seq']}x with {MPI_NP} processes")


if __name__ == "__main__":
    main()
