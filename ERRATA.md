# Errata for `report.pdf` (Operating Systems, Assignment 4, 30 November 2025)

`report.pdf` is preserved unchanged as the historical submission. A later audit of the code and data (see [docs/ENGINEERING_NOTES.md](docs/ENGINEERING_NOTES.md)) shows that the statements below are not supported or do not match the repository. Each item gives the
evidence.

| # | Report location | Statement | Status and evidence |
|---|---|---|---|
| 1 | §3.4 (MPI paragraph "Large matrices"), §5 Conclusion | MPI "is most effective" for large matrices and "shows the strongest scaling … surpass[es] all other models". | **Not supported.** The MPI timings (0.071 s at 500², 0.094 s at 2000², 0.247 s at 5000²) imply speedups of 14×, 1 134× and 9 202× on 4 processes, which is physically impossible (limit ≈ 4×). They match the signature of a failed `mpirun` launch: with fewer slots than processes OpenMPI exits after ≈ 0.06 s (reproduced), and `Test-Script.sh` discarded the error message. Output was never compared with the sequential result. The same applies to the 500 000-element sort (0.061 s, 5.4× on 4 processes). |
| 2 | §3.3 item 4–5 | "Only computational runtime was measured; printing … was disabled to eliminate I/O interference." | **Inaccurate.** `time` measured the whole process. Output was redirected to `/dev/null`, but the program still read and parsed the input text file and formatted every result element. Input parsing is serial and dominates for small sizes. The validated harness now records both whole-process (`wall_s`) and in-program compute (`kernel_s`) times. |
| 3 | §3.3.1 | The test script's `-f` check was "changed to `-s`". | **Does not match the repository.** `matrix_multiplication/Test-Script.sh` as committed (before the audit) used `-f`. (The rewritten script now uses `-s`.) |
| 4 | §3.1 step 2 | Compilation shown as `gcc sequential.c matrix.c -o sequential.out` etc. (no optimisation flags). | The benchmark script actually builds through the Makefile with `-O2`; the two descriptions differ. Results correspond to the Makefile build. |
| 5 | §4.6 (OpenMP recursive merge sort) | Describes parallel recursion via `#pragma omp parallel sections` with a depth bound. | The nested regions are inactive under the default OpenMP setting `max-active-levels = 1` (verified: inner team size 1), so that implementation ran effectively sequentially unless `OMP_MAX_ACTIVE_LEVELS` was raised. Conclusions about OpenMP merge-sort speedups from the original data are therefore not meaningful. The implementation is now task-based. |
| 6 | §4.5, §4.7, §4.10 | Pthreads/MPI merge-sort results. | The previous `mpi.c` returned a wrongly sorted array (exit code 0) when n was not divisible by the process count; in an audit reproduction this affected **n = 10 with 4 processes**, a size in the report's table (n = 5 happened to come out correct; 500, 2 000, 5 000 and 500 000 are divisible by 4). The previous `thread2.c` hung when the array had fewer elements than cores, so its small-size results depend on the (unrecorded) core count of the original machine. |

What remains supported: at small inputs all parallel variants are slower than sequential (start-up cost), and
OpenMP/Pthreads matrix multiplication was about 1.7–2.0× faster than sequential at 2000² and 5000² on the original
machine.
