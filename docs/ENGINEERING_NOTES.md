# Engineering notes

How the original code was audited, which defects were found, and how the repository now prevents them from coming back.
"Original code" means the repository at commit `25432a3` (the state submitted with `report.pdf`); file references below
are to that commit.

## 1. Defects that affected results

| ID | Location | Problem and evidence | Fix |
|---|---|---|---|
| C1 | `merge_sort/src/mpi.c` (chunk computation, `MPI_Scatter`/`MPI_Gather`, lines 50–82) | The chunk size was rounded up, the padding was scattered and sorted, and only the first n elements were merged. **The output was wrong with exit code 0 whenever n was not divisible by the rank count** (reproduced for n = 3, 5, 10, 11, 1001, 2000 with 2–7 ranks). | `MPI_Scatterv`/`MPI_Gatherv` with run-boundary merging; regression tests over six sizes and four rank counts. |
| C2 | `merge_sort/src/omp.c` (nested `#pragma omp parallel sections`, lines 26–61) | OpenMP runtimes default to one active parallel level, so every nested region ran on a team of one. Instrumentation showed team size 1 (and 4 with `OMP_MAX_ACTIVE_LEVELS=8`): the sort was sequential whatever `OMP_NUM_THREADS` said. | Task-based sort with a sequential cut-off; a test asserts that several threads execute leaf sorts. |
| C3 | `merge_sort/src/thread2.c` (chunk and merge loop, lines 56–90) | With fewer elements than cores the chunk size was 0 and the merge loop never advanced: an **infinite hang** (reproduced with 8 simulated cores for n = 1, 2, 3, 5, 7). | Thread count capped at n; balanced partition. |
| C4 | `*/Test-Script.sh` (`time mpirun … \| grep real`) | A failed `mpirun` (OpenMPI: "not enough slots", exit in ≈0.06 s on a machine with fewer slots than ranks — reproduced) was timed as if it were a result, and outputs were never compared with the sequential output. MPI timings produced this way imply speedups far beyond the process count and cannot be used. | Scripts print `FAILED`; the harness checks exit status and output hash for every run. |

## 2. Robustness and portability defects

| ID | Location | Problem | Fix |
|---|---|---|---|
| M1 | `matrix_multiplication/src/mpi.c` | Aborted unless rows % ranks == 0. | Balanced row distribution for any rank count. |
| M2 | `merge_sort/src/array.c` | `fscanf` stopped silently at a non-integer token (`3 1 abc 2` became `[3, 1]`). | Detected; error on stderr, non-zero exit. |
| M3 | `matrix_multiplication/src/matrix.c` | A final row without a newline was dropped; `!fscanf(...)` treats EOF as success, so truncated files became zeros. | Last row counted; return value checked; clear errors. |
| M4 | `matrix.c`, `sequential.c`, `omp.c`, `thread2.c` (line 3) | `<malloc.h>` does not exist on macOS. | Removed. |
| M5 | `.gitkeep` (root) | Contained `.gitignore` rules, so nothing was ignored and 0.5 GB test matrices could be committed. | Proper `.gitignore`. |
| M6 | `matrix_multiplication/Makefile` | Dead `thread` target; no `mkdir -p bin`; no floating-point contraction policy (on FMA hardware different models can round differently and fail a byte-wise comparison). | Fixed; `-ffp-contract=off` everywhere. |
| M7 | four copies of `merge()` | Duplicated, so the models did not share one sorting kernel. | One shared kernel (`msort.c`). |
| M8 | whole-process timing | `mpirun` start-up and serial text parsing dominate small and medium sizes. | In-program kernel time recorded next to wall time. |

## 3. How correctness is guaranteed now

- **Run validation.** Every benchmark run is classified `ok` / `failed` / `mismatch` / `timeout` / `no_reference` from its exit
  code and the SHA-256 of its output against the sequential output for the same input. Only `ok` runs are aggregated.
- **Independent oracles.** Regression tests compare every model with Python (`sorted()` and a pure-Python matrix product
  with the same summation order, bit-for-bit) on awkward inputs: empty, fewer elements than threads, sizes not divisible
  by the rank count, non-square matrices, malformed files, missing trailing newline.
- **Sanitizers.** AddressSanitizer and UndefinedBehaviorSanitizer builds of the non-MPI binaries run in CI; all eight
  binaries were also run under them during development with no findings.
- **Timeouts.** The harness drains stdout and stderr in reader threads and enforces the timeout with a process-group kill,
  so a silent hang (for example an MPI deadlock) cannot block a benchmark; a regression test covers it.
- **Environment capture.** CPU, physical/logical/effective cores, container CPU quota, OS, compiler and MPI versions,
  compiler flags (parsed from the Makefiles), data seed, input hashes, git commit and a free-text note are stored with every
  result set.
- **Oversubscription.** More workers than physical cores is flagged for every model and excluded from `scaling_valid`.

## 4. Incident: CI failure on a newer Open MPI

The first CI run on `ubuntu-latest` (by then Ubuntu 26) failed in the MPI regression tests with
`prte-rmaps-base:alloc-error` ("not enough slots"). That image launches MPI jobs through PRRTE's `prterun`, whose
`--version` never prints "Open MPI"; the harness inferred the launcher type from that text, concluded "unknown" and added no
oversubscribe flag. The same flag also exists in different spellings across Open MPI releases (`--oversubscribe` is the
classic one; `--map-by :oversubscribe` is the native PRRTE form and the classic one only warns there). The failure was
reproduced locally with Open MPI 5.0.11 behind a `prterun` wrapper. The fix replaces inference by probing: the harness
launches a trivial program oversubscribed and keeps the first flag spelling that works without warnings. Unit tests use
fake launchers for the three behaviours (classic flag, PRRTE-style, no flag understood).

## 5. Known limitations and residual risks

1. The matrix kernel keeps the cache-unfriendly `i-j-k` loop order of the upstream scaffold. A different order (for example
   `i-k-j`, which preserves each element's summation order) would be much faster but would change the baseline; it is
   documented rather than changed.
2. Matrix MPI broadcasts full A and B to every rank (inherited design); `int` message counts limit a matrix to roughly
   46 000 × 46 000 elements per side.
3. MPI runs are single-node; they do not measure network scaling.
4. Platforms exercised: Ubuntu 24.04 (WSL2) with Open MPI 4.1.6 and the PRRTE-style launcher described above. macOS, MPICH and
   native Windows are untested; the MPICH path (no oversubscribe flag found) degrades to recording such runs as failed.
5. GitHub Actions are pinned to major versions rather than commit SHAs.
