# Parallel Computing Benchmark: Merge Sort & Matrix Multiplication

![C](https://img.shields.io/badge/C-gnu99-blue.svg)
![OpenMP](https://img.shields.io/badge/OpenMP-tasks-orange.svg)
![Pthreads](https://img.shields.io/badge/POSIX-Pthreads-green.svg)
![MPI](https://img.shields.io/badge/MPI-OpenMPI-red.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
[![CI](https://github.com/Namra-5/parallel_sorting_and_matrix_benchmark/actions/workflows/benchmark-smoke.yml/badge.svg)](https://github.com/Namra-5/parallel_sorting_and_matrix_benchmark/actions/workflows/benchmark-smoke.yml)

A comparative study of **four execution models** — Sequential, OpenMP, POSIX Threads (Pthreads) and MPI — on two classic
workloads: **Merge Sort** (memory-bound, O(n log n)) and **Matrix Multiplication** (compute-bound, O(n³)).

The project began as a course assignment ([report.pdf](./report.pdf), Operating Systems, NUST) and was then rebuilt around a
single rule: **a measurement counts only if the program exited cleanly and printed exactly the same answer as the
sequential program.** Everything here — the C implementations, the benchmark harness, the statistics, the tests and the CI —
is organised to make that rule automatic, so that scaling results are trustworthy and reproducible by anyone.

---

## Table of Contents

- [What is validated](#what-is-validated)
- [Execution models](#execution-models)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Reproducing the scaling benchmark](#reproducing-the-scaling-benchmark)
- [Measurement methodology](#measurement-methodology)
- [Problems found and fixed](#problems-found-and-fixed)
- [Limitations](#limitations)
- [Citation](#citation)
- [Tech stack](#tech-stack) · [Author](#author) · [Acknowledgments](#acknowledgments) · [License](#license)

---

## What is validated

| Guarantee | How it is enforced |
|---|---|
| Every parallel run is checked | `benchmark/run_benchmark.py` records the exit code and a SHA-256 of stdout for every run and compares it with the sequential output for the same input. Only `ok` runs enter any statistic. |
| Failed or hung launches cannot look fast | Non-zero exits, wrong output and timeouts get their own status and are excluded; the timeout kills the whole process tree. |
| Correct for awkward sizes | Regression tests build every binary and compare it with an independent Python oracle (empty input, fewer elements than threads, sizes not divisible by the rank count, non-square matrices, malformed files). |
| Scaling claims are honest | Configurations with more workers than physical cores are flagged `oversubscribed` and excluded from `scaling_valid`. |
| Reproducible | Seeded generators, input SHA-256 manifest, recorded hardware/compiler/MPI/git state, identical floating-point policy (`-ffp-contract=off`). |
| Memory safe | The non-MPI binaries are built and run under AddressSanitizer + UndefinedBehaviorSanitizer in CI (`make EXTRA_CFLAGS="-fsanitize=address,undefined"`); the MPI binaries were checked the same way during development. |

CI ([`benchmark-smoke.yml`](.github/workflows/benchmark-smoke.yml)) runs the unit tests, the regression tests, a smoke
benchmark and the sanitizer build on every pull request and every push to `main`.

---

## Execution models

| Model | Type | Memory | Implementation notes |
|---|---|---|---|
| Sequential | Baseline | Single thread | Reference for correctness *and* for every speedup |
| OpenMP | Shared memory | Threads | Matrix: `#pragma omp parallel for` over rows. Sort: **task-based** merge sort with a sequential cut-off |
| Pthreads | Shared memory | Threads | Explicit balanced partitioning; thread count from `BENCH_THREADS` (default: online CPUs) |
| MPI | Distributed memory | Processes | Matrix: broadcast of A and B, balanced row blocks, `MPI_Gatherv`. Sort: `MPI_Scatterv` → local sort → `MPI_Gatherv` → merge. Works for any rank count |

The four sorting binaries share **one** merge kernel (`merge_sort/src/msort.c`), so the comparison measures the
parallelisation strategy rather than four slightly different sort routines.

---

## Project structure

```
.
├── common/bench_common.h        # kernel timer + thread-count helper shared by all binaries
├── merge_sort/
│   ├── src/ array.c/.h  msort.c/.h  sequential.c  omp.c  thread2.c  mpi.c
│   ├── Makefile  random_array.py  Test-Script.sh  bin/  data/
├── matrix_multiplication/
│   ├── src/ matrix.c/.h  sequential.c  omp.c  thread2.c  mpi.c
│   ├── Makefile  random_float_matrix.py  Test-Script.sh  bin/  data/
├── benchmark/
│   ├── run_benchmark.py         # validated driver -> results/raw_runs.csv
│   ├── standardize.py           # raw runs -> results/benchmark_results.csv (speedup, efficiency)
│   ├── plot_results.py          # speedup figures from the results CSV
│   ├── tests/                   # unit + regression tests
│   └── README_BENCHMARK.md      # dataset schema and interpretation guide
├── docs/ENGINEERING_NOTES.md    # defects found, evidence, fixes, residual risks
├── .github/workflows/benchmark-smoke.yml
└── report.pdf  ERRATA.md  CHANGELOG.md  CITATION.cff  NOTICE  LICENSE
```

---

## Prerequisites

- Linux, macOS or Windows via **WSL**
- `gcc` with OpenMP (libgomp ships with gcc; `libomp-dev` is only needed for clang), `make`
- `mpicc` / `mpirun` (Open MPI), `python3` ≥ 3.9 (tested with 3.12 and 3.13) with `pandas` (`matplotlib` for plots, `pytest` for tests)

```bash
sudo apt update && sudo apt install build-essential libopenmpi-dev openmpi-bin python3 python3-pip
python3 -m pip install -r benchmark/requirements.txt
```

---

## Quick start

```bash
python3 -m pytest benchmark/tests -q                              # unit + regression tests
python3 benchmark/run_benchmark.py --smoke --out-dir /tmp/smoke   # ~10 s end-to-end check
```

---

## Reproducing the scaling benchmark

```bash
python3 benchmark/run_benchmark.py --workload both \
    --matrix-sizes 500 1000 1500 --sort-sizes 50000 500000 5000000 --workers 1 2 4 --reps 5 --cooldown 20 \
    --notes "describe the machine: bare metal / WSL2 / VM, power mode, background load"
python3 benchmark/standardize.py        # -> benchmark/results/benchmark_results.csv
python3 benchmark/plot_results.py       # -> benchmark/results/*.png
```

`--workers` defaults to 1, 2, 4, … up to the physical core count; `--cooldown` pauses between repetitions, which helps on thermally limited laptops. Outputs (`raw_runs.csv`, `benchmark_results.csv`,
`hardware_environment.json`, `inputs_manifest.json`) are described in [benchmark/README_BENCHMARK.md](benchmark/README_BENCHMARK.md).
Select only rows with `scaling_valid == True` when making scaling claims.

---

## Measurement methodology

- **Two times per run.** `wall_s` is the whole process (includes `mpirun` start-up, parsing the text input and printing).
  `kernel_s` is measured *inside* the program (`BENCH_TIMING=1`) and covers computation only (for MPI also
  scatter/gather/merge). Input parsing is serial, so `wall_s` understates achievable speedup (Amdahl's law); `kernel_s` is
  the scaling signal.
- **Speedup / efficiency.** `S_N = T_seq / T_N` against the true sequential binary on the same workload and size;
  `E_N = S_N / N`. `speedup_vs_1worker` uses the same model with one worker. Medians over valid repetitions.
- **Run order.** Repetitions are the outer loop so slow drift (thermal, background load) affects all models alike.
- **Compiler.** `-O2 -Wall -std=gnu99 -g -fopenmp -ffp-contract=off` for every model; no model-specific tuning.
- **Known simplification.** The matrix kernel keeps the textbook `i-j-k` loop order (inherited from the upstream
  scaffold), which is cache-unfriendly; absolute times are therefore much slower than a tuned BLAS. All models share it,
  so relative comparisons remain valid, but the figures are not a statement about peak hardware performance.

---

## Problems found and fixed

While preparing the project for publication as a reproducible dataset, a code audit showed that parts of the original
measurements could not be trusted. MPI runs that failed to launch had been timed as if they were results, the "OpenMP"
merge sort ran on a single thread, and the MPI merge sort silently returned wrongly sorted arrays for some input sizes.
These defects were fixed, pinned down by regression tests, and the measurement pipeline was rebuilt so that a run only
counts if it exits cleanly and reproduces the sequential output. The statements of the original report affected by this are
listed in [ERRATA.md](./ERRATA.md); full evidence and residual risks are in [docs/ENGINEERING_NOTES.md](docs/ENGINEERING_NOTES.md).

| # | Problem (evidence) | Fix |
|---|---|---|
| 1 | **Failed MPI launches were timed as results.** With fewer slots than processes, `mpirun` exits in ≈0.06 s with "not enough slots"; the old script discarded that error. | Harness checks exit status and output hash; scripts print `FAILED`; oversubscribed runs get the right launch flag and are flagged. |
| 2 | `merge_sort/src/mpi.c` returned a **wrongly sorted array with exit code 0** whenever n was not divisible by the rank count. | `MPI_Scatterv`/`Gatherv`; regression tests. |
| 3 | The "OpenMP" merge sort **ran on one thread**: nested `parallel sections` are inactive under the default `max-active-levels=1` (verified by instrumentation). | Task-based sort; a test asserts that several threads execute work. |
| 4 | `merge_sort/src/thread2.c` **hung forever** when elements < cores. | Thread count capped at n, balanced split. |
| 5 | The MPI matrix code aborted unless rows % ranks == 0. | Row distribution for any rank count. |
| 6 | Parsers accepted bad input silently: a non-integer token truncated the array, a missing final newline dropped the last matrix row, a truncated matrix became zeros. | Explicit errors on stderr and a non-zero exit. |
| 7 | A root-level `.gitkeep` contained `.gitignore` rules and so ignored nothing. | A real `.gitignore` (data, binaries). |
| 8 | `<malloc.h>` does not exist on macOS. | Removed. |
| 9 | Four duplicated `merge()` copies. | One shared kernel. |
| 10 | A CI run on a newer Open MPI (PRRTE launcher, whose `--version` never says "Open MPI") exposed fragile launcher detection: no oversubscribe flag was added. | Launch flags are now **probed** by test launches, not inferred from version text; covered by tests with fake launchers. |

---

## Limitations

- Results depend on the machine; always read `hardware_environment.json` next to a result file.
- Wall time includes serial text I/O and (for MPI) process launch; kernel time excludes input parsing and output printing.
- MPI runs are single-node (shared-memory transport): they measure process-level parallelism, not network scaling.
- Sorting uses a serial final merge (an inherent Amdahl limit); matrix MPI broadcasts full A and B to every rank.
- Hyper-threads are not counted as cores: more workers than physical cores is reported as oversubscribed.
- Tested on Ubuntu 24.04 under WSL2 (Open MPI 4.1.6) and on GitHub's Ubuntu runner (PRRTE-based Open MPI launcher). macOS, MPICH and native Windows have not been tested.

---

## Citation

If you use this software or its data, please cite it using [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository"
button). A DOI is issued with each tagged release through Zenodo.

---

## Tech stack

`C (gnu99)` · `OpenMP` · `POSIX Threads` · `MPI (Open MPI)` · `Python 3` (pandas, matplotlib, pytest) · `Bash` · `GNU Make` · `GitHub Actions`

---

## Author

**Namra Basharat** — BS Bioinformatics, National University of Sciences and Technology (NUST), School of Interdisciplinary
Engineering & Sciences. Course: Operating Systems.

## Acknowledgments

The matrix-multiplication scaffold (`matrix.c/.h`, the original per-model programs, `Makefile`, `Test-Script.sh`,
`random_float_matrix.py`) is adapted from [mperlet/matrix_multiplication](https://github.com/mperlet/matrix_multiplication)
(MIT, © 2022 Mathias Perlet; generator by Philipp Böhm). Modifications are listed in [NOTICE](./NOTICE) and
[CHANGELOG.md](./CHANGELOG.md). The merge-sort programs, the benchmark tooling, tests and analysis are original work.

## License

[MIT](./LICENSE) — third-party notice in [NOTICE](./NOTICE).
