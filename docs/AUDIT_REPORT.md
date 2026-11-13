# Audit report — parallel_sorting_and_matrix_benchmark

Scope: every C source, Makefile, shell script, Python tool, test and workflow in the repository
(`parallel_sorting_and_matrix_benchmark-main.zip`) and in the proposed additions (`parallel_sorting_and_matrix_benchmark.zip`),
plus `README.md`, `report.pdf` and the two charts. Line numbers refer to the files **as received**.
Environment used for testing: Ubuntu 24.04, gcc 13.3, OpenMPI 4.1.6, Python 3.12, **1 CPU core** (the same situation as a
single-core CI runner). Not tested: macOS, MPICH, native Windows/WSL, any machine with more than one core.

## Verified correct (no change needed)
- `NOTICE`: the embedded licence text is byte-identical (whitespace-normalised) to upstream `mperlet/matrix_multiplication/LICENSE`
  (MIT, "Copyright (c) 2022 Mathias Perlet"), fetched from GitHub during the audit.
- The upstream-derived matrix C files differ from upstream by 0–2 lines each, so attribution as "adapted from" is accurate.
- The README_BENCHMARK arithmetic (implied MPI speedups 14×, 1 134×, 9 202×, 5.4×) is correct, and the failed-launch claim is
  reproduced: `mpirun -np 4` without `--oversubscribe` on 1 core exits 1 after **0.061 s** ("not enough slots"), inside the
  0.061–0.094 s band of the legacy MPI timings. That the original machine behaved this way is an inference and is labelled as such.
- Compiler flags are `-O2` (not `-O3`), so the flag-driven UB risks are low. Results are printed, so dead-code elimination of
  the product/sort is not a concern. `-fopenmp`/`-pthread`/`mpicc` usage is correct on Linux.
- The shipped harness ran cleanly on 1 core (16/16 valid) and its 10 unit tests passed.
- `libomp-dev` is **not** needed: it provides OpenMP for clang; gcc uses libgomp, which ships with `build-essential`.
  `python3` comes from `actions/setup-python`. The proposed apt list was sufficient for the first CI run.

## CRITICAL (wrong results or invalid science)

| ID | Where (as received) | Problem and evidence | Fix |
|---|---|---|---|
| C1 | `merge_sort/src/mpi.c` 50–61, 63–82 | Rounds the chunk up, scatters from an array of n elements, sorts the padding, merges with `real = n`. **Output is wrong with exit code 0 whenever n % ranks ≠ 0** (reproduced: n = 3, 5 (np 2), 10 (np 3, 4), 11, 1001, 2000 (np 3, 7)). n = 10 with 4 processes is in the README table. | `Scatterv`/`Gatherv`, run-boundary merge; test over 6 sizes × 4 rank counts. |
| C2 | `merge_sort/src/omp.c` 26–38, 54–61 | Nested `parallel sections`. libgomp's default `max-active-levels` is 1; instrumented run: **team size 1** (4 with `OMP_MAX_ACTIVE_LEVELS=8`). The "OpenMP" sort ran sequentially, so `OMP_NUM_THREADS` sweeps are flat and the legacy OpenMP sort numbers do not measure OpenMP. | Task-based sort; test asserts several threads run leaf sorts. |
| C3 | `benchmark/run_benchmark.py` 53–80 | `p.stdout.read(1<<20)` blocks until 1 MiB or EOF; the deadline is only checked afterwards. Reproduced: a silent 25 s hang with `timeout=3` returned **after 25 s as exit 0, timed_out=False**; an MPI deadlock would hang forever. | Reader threads, `Popen.wait(timeout)`, process-group kill; regression tests. |
| C4 | `merge_sort/src/thread2.c` 56–90 | For n < cores `chunk = 0` and the merge loop never advances: **infinite hang** (reproduced with 8 simulated cores for n = 1, 2, 3, 5, 7; n ≥ 8 was correct). The README's sizes 5 and 10 therefore hang on any machine with more than 5 / 10 online CPUs. | Thread count ≤ n, balanced split. |
| C5 | `*/Test-Script.sh` (`time mpirun … \| grep real`: matrix lines 75, 90, 105, 120, 135; merge sort lines 51, 65, 79, 93, 107, 121); README 36–37, 150–158, 200; `report.pdf` §5 | Failure of `mpirun` is discarded and its duration printed as a result; conclusions ("MPI strongest scaling / best for large inputs") rest on it. Only 4 of the 11 legacy MPI rows were flagged by `legacy_extract.py`, although all 11 share the signature and none was verified. | Scripts report FAILED; README rewritten; all MPI rows flagged; charts redrawn; `ERRATA.md`. Note in fairness: your original README already caveated the large MPI cells (footnote ¹ at line 158 and the note at line 200) as unverified; the audit shows the problem is broader (all MPI cells, and the "best model" table at lines 36–37). |

## MODERATE

| ID | Where | Problem | Fix |
|---|---|---|---|
| M1 | `matrix_multiplication/src/mpi.c` 50–53 | Aborts unless rows % ranks == 0 (e.g. 500 rows with 3 or 6 ranks). Loud failure, but makes natural worker counts unusable. | Any rank count. |
| M2 | `merge_sort/src/array.c` 14, 17–19 | `fscanf` stops silently at a non-integer: `3 1 abc 2` becomes `[3, 1]`. | Detect and exit with message. |
| M3 | `matrix.c` 19–33, 48 | A final row without newline is dropped silently (reproduced); `!fscanf(...)` treats EOF (−1) as success, so truncated files become zeros. | Count last row; check `!= 1`; clear errors. |
| M4 | `run_benchmark.py` 143–148, 166 | `os.cpu_count()` counts hyper-threads and ignores affinity/containers, whereas OpenMPI's default slot count is physical cores, so `-np` between physical and logical cores fails or is mis-flagged. `--oversubscribe`/`--allow-run-as-root` are OpenMPI-only yet the README promises MPICH. OpenMP/thread oversubscription never flagged. | Effective-core detection, MPI flavour detection, `oversubscribed` for every model. |
| M5 | `standardize.py` 17–33 | Only the sequential baseline (correctly matched on workload+size). No same-model T₁ baseline; oversubscribed rows indistinguishable from valid scaling; partial failures reported as `ok`. | `speedup_vs_1worker`, `PARTIAL`, `scaling_valid`. |
| M6 | `run_benchmark.py` 153–end (`main` never sets an exit status), 201 | Exit code 0 even if runs failed (only CI's extra script noticed). `raw_runs.csv` written only at the very end (line 201), so a crash in a multi-hour run loses everything. | Exit 1; incremental writing. |
| M7 | `tests/test_benchmark.py` 46–47, `legacy_extract.py` 55 | The test rewrites the committed CSV in the repository (and with CRLF endings) each run. | `--out` option, temp files, drift-guard test. |
| M8 | `.gitkeep` (root) | Contains ignore rules, so nothing was ignored; `matrix_multiplication/data/*.txt` (0.5 GB each at 5000²) could be committed by accident. The proposed `.gitignore` did not cover `*/data/`. | Proper `.gitignore`. |
| M9 | `thread2` hard-coded thread count; harness ran it once | Pthreads could not be swept; its "workers" was the core count. | `BENCH_THREADS`. |
| M10 | whole-process timing only | `mpirun` start-up (~0.4 s here) and serial text parsing dominate small and medium sizes; report §3.3 claims otherwise. | `kernel_s` recorded in-process. |
| M11 | `matrix.c:3`, `sequential.c:3`, `omp.c:3`, `thread2.c:3` | `<malloc.h>` does not exist on macOS. | Removed. |
| M12 | CI workflow | No `permissions`, no `timeout-minutes`, runs on push **and** PR (duplicate runs), no sanitizer job. | Hardened. |
| M13 | Makefiles | `thread` target builds a non-existent `src/thread.c`; no `mkdir -p bin`; no FP-contraction policy (on ARM/FMA targets, models can round differently and fail the byte-wise comparison). | Fixed; `-ffp-contract=off`. |

## MINOR
- Four copies of `merge()` (now one kernel); `thread2.c` leaked the per-thread structs and the handle array; a dead `count++` in the hot loop.
- Error messages on stdout (now stderr). Generators unseeded; the harness seeded them through a `runpy` hack (now an optional seed
  argument; previously cached data is byte-identical, verified).
- `hardware()` recorded a hard-coded flags string that could drift from the Makefile (now parsed). Missing `lscpu`/`/proc/meminfo` did not
  crash (verified) but gave empty fields on macOS (now `sysctl`). Native Windows is unsupported (message added).
- `LICENSE` said 2025 while NOTICE said 2025–2026; NOTICE did not list modifications to upstream files.
- Security (OWASP view; this is a local CLI, so the relevant items are input handling, memory safety and CI hygiene): no shell is used
  by the harness (argument lists, no injection surface); C parsers now validate input and check allocations; integer overflow in
  `rows*cols` indexing replaced by `size_t`; ASan/UBSan clean on all eight binaries; workflow has least-privilege `permissions`.
  Remaining recommendation: pin GitHub Actions to commit SHAs.

## Residual risks and recommendations
1. **No real scaling dataset exists yet.** A 1-core machine cannot measure scaling; run the commands in `APPLY_STEPS.md` on your own
   multi-core machine and publish `hardware_environment.json` with the CSVs.
2. The matrix kernel keeps the cache-unfriendly `i-j-k` order from upstream. Changing it (e.g. `i-k-j`, which keeps summation order and
   byte-identical output) would make runs far faster, but changes the baseline relative to the report, so it was documented, not changed.
3. Not tested here: macOS (needs `brew install gcc open-mpi`), MPICH, native Windows. Open MPI 4.1.6 (Ubuntu 24.04, WSL) and Open MPI 5.0.11 / PRRTE (the Ubuntu 26 CI runner's launcher) were exercised. The MPICH path (no oversubscribe flag found) exists but
   were verified only by unit tests of the command construction.
4. Input broadcast in matrix MPI sends full A and B to every rank (design inherited from upstream); `int` counts limit matrices to
   about 46 000 × 46 000 elements per side.

## Post-release correction (found by CI)
The first GitHub Actions run failed on `ubuntu-latest` (by then Ubuntu 26, Open MPI 5 with an external PRRTE). My harness chose MPI launch flags from the `mpirun --version` text; that launcher prints "prterun (PRRTE)", so no oversubscribe flag was added and every `-np` above the slot count failed with `prte-rmaps-base:alloc-error` ("not enough slots"). I had only tested Open MPI 4.1.6. Fix: flags are discovered by launching a trivial program oversubscribed and keeping the first spelling that works cleanly. Reproduced locally with Open MPI 5.0.11 behind a `prterun` wrapper, fixed, and covered by unit tests with fake launchers.

## Review method
Beyond the checklist I did a structured multi-perspective pass (HPC engineer, security reviewer, scientific-methods reviewer, and an
admissions-committee reader). This was a single reviewer role-playing these views, not several independent models. Outcome: the
decisive credibility gain is not new features but demonstrating that invalid data was found, explained, quarantined and prevented
from recurring; the README, ERRATA, tests and CI now tell that story, and nothing is claimed that was not measured.
