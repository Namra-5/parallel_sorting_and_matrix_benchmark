# Changelog

## 2.0.0 — audit and validation release

### Fixed (correctness)
- CI on Ubuntu 26 (Open MPI 5, where `mpirun` is PRRTE's `prterun` and never prints "Open MPI"): the harness did not recognise the launcher, added no oversubscribe flag, and `mpirun -np 3` failed with "not enough slots". Flags are now probed, not inferred from version text; regression-tested with fake launchers and verified against Open MPI 4.1.6 and 5.0.11.
- `merge_sort/src/mpi.c`: wrong output with exit code 0 when n % ranks != 0 → `MPI_Scatterv`/`Gatherv` (any n, any ranks).
- `merge_sort/src/omp.c`: nested `parallel sections` ran on one thread (default `max-active-levels = 1`) → tasks with cut-off.
- `merge_sort/src/thread2.c`: hang for n < cores → thread count capped at n, balanced partition.
- `matrix_multiplication/src/mpi.c`: required rows % ranks == 0 → any rank count; uses `size_t` for index arithmetic.
- `matrix_multiplication/src/thread2.c`: balanced row split, no per-thread leaks, explicit thread count.
- Input parsing: non-integer tokens, empty/truncated matrices and a missing final newline are now detected (stderr, non-zero exit).
- `Test-Script.sh` (both): failed runs are reported as FAILED instead of being timed.

### Added
- `common/bench_common.h` (kernel timer, `BENCH_THREADS`), `merge_sort/src/msort.[ch]` (one shared sorting kernel).
- Harness: MPI launch flags found by probing `mpirun` with a trivial oversubscribed launch (works for Open MPI 4, Open MPI 5 / PRRTE, and degrades cleanly for MPICH), effective-core detection (affinity, SMT, cgroup quota), `oversubscribed` flag
  for every model, `kernel_s`, incremental `raw_runs.csv`, input manifest, git/compiler/MPI/hardware record, exit code 1 on invalid runs.
- `standardize.py`: baselines matched on workload+size(+model), `speedup_vs_1worker`, kernel speedups, `PARTIAL` status, `scaling_valid`.
- `plot_results.py`, `docs/ENGINEERING_NOTES.md`, tests (unit + regression with Python oracles), sanitizer CI job, `ERRATA.md`, `CITATION.cff`.
- Optional seed argument for both data generators (cached data from the earlier harness is byte-identical).

### Changed
- Makefiles: `-ffp-contract=off`, `mkdir -p bin`, `.PHONY`, `EXTRA_CFLAGS`, removed the dead `thread` target.
- `<malloc.h>` removed (macOS portability); error messages go to stderr.
- README rewritten around validated measurements; the 2025 result tables and charts were removed (the affected statements of the report are listed in `ERRATA.md`).
- Root `.gitkeep` (which held ignore rules) replaced by a working `.gitignore`.
- NOTICE lists the modifications to upstream files; LICENSE year range aligned with NOTICE.

### Note on comparability
The sorting binaries now share one kernel that uses a single scratch buffer instead of two `malloc`s per merge, so absolute
sorting times are not comparable with measurements made with the earlier code.
