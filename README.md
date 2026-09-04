# Parallel Computing Benchmark: Merge Sort & Matrix Multiplication

![C](https://img.shields.io/badge/C-gnu99-blue.svg)
![OpenMP](https://img.shields.io/badge/OpenMP-parallel-orange.svg)
![Pthreads](https://img.shields.io/badge/POSIX-Pthreads-green.svg)
![MPI](https://img.shields.io/badge/MPI-OpenMPI-red.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

A comparative benchmark of **four execution models** — Sequential, OpenMP, POSIX Threads (Pthreads), and MPI — applied to two classic workloads: **Merge Sort** (memory-bound, O(n log n)) and **Matrix Multiplication** (compute-bound, O(n³)).

The project measures how each parallel programming paradigm behaves as input size scales, and empirically shows *when* parallelism helps and when its overhead outweighs the benefit.

**[Full written report (PDF) →](./report.pdf)** — includes methodology, per-model analysis, and complexity derivations.

---

## Table of Contents

- [Key Results](#key-results)
- [Execution Models](#execution-models)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Build & Run](#build--run)
- [Benchmark Results](#benchmark-results)
- [Notes & Caveats](#notes--caveats)
- [Tech Stack](#tech-stack)
- [Author](#author)
- [License](#license)

---

## Key Results

| Workload | Best model (small input) | Best model (large input) | Why |
|---|---|---|---|
| Matrix Multiplication | Sequential | MPI (4 processes) | Compute grows as O(n³); at large `n`, arithmetic dominates communication cost |
| Merge Sort | Sequential | Pthreads / MPI | Sort grows as O(n log n); overhead from thread/process setup dominates until arrays are large |

**Takeaway:** parallel execution is only worthwhile once the useful work per worker outweighs the cost of creating and coordinating that worker. All four models were benchmarked across 5–6 input sizes per workload to make this crossover point visible (see [Benchmark Results](#benchmark-results)).

---

## Execution Models

| Model | Type | Memory | Key Points |
|---|---|---|---|
| Sequential | Baseline | Single-threaded | Reference implementation for correctness; minimal overhead |
| OpenMP | Shared-memory | Threads | Pragma-based (`#pragma omp`); compiler-managed scheduling |
| Pthreads | Shared-memory | Threads | Manual thread creation and explicit workload partitioning |
| MPI | Distributed-memory | Processes | Scales across nodes; communication cost dominates at small sizes |

> Parallelism improves runtime only when the **amount of useful work offsets concurrency management costs**.

---

## Project Structure

```
.
├── merge_sort
│   ├── bin/            # compiled binaries (seq, omp, thread2, mpi)
│   ├── data/            # generated test arrays (5 .. 500000 elements)
│   ├── src/
│   │   ├── array.c / array.h   # shared I/O utilities
│   │   ├── sequential.c
│   │   ├── omp.c
│   │   ├── thread2.c
│   │   └── mpi.c
│   ├── Makefile
│   ├── random_array.py
│   └── Test-Script.sh
├── matrix_multiplication
│   ├── bin/
│   ├── data/            # generated test matrices (5x4 .. 5000x5000)
│   ├── src/
│   │   ├── matrix.c / matrix.h
│   │   ├── sequential.c
│   │   ├── omp.c
│   │   ├── thread2.c
│   │   └── mpi.c
│   ├── Makefile
│   ├── random_float_matrix.py
│   └── Test-Script.sh
├── report.pdf
├── README.md
└── LICENSE
```

---

## Prerequisites

- Linux (tested on Ubuntu)
- `gcc` with OpenMP support (`-fopenmp`)
- `mpicc` / `mpirun` (OpenMPI or MPICH)
- `python3`
- POSIX `time` utility (used by the test scripts)

Install on Debian/Ubuntu:

```bash
sudo apt update
sudo apt install build-essential libopenmpi-dev openmpi-bin python3
```

---

## Build & Run

### Merge Sort

```bash
cd merge_sort
chmod +x Test-Script.sh
./Test-Script.sh
```

### Matrix Multiplication

```bash
cd matrix_multiplication
chmod +x Test-Script.sh
./Test-Script.sh
```

Each script will:
1. Generate any missing test data with the Python generator.
2. Compile all four binaries via `make` (`bin/seq`, `bin/omp`, `bin/thread2`, `bin/mpi`).
3. Run every binary against every input size and print wall-clock (`real`) time.

Build manually instead of via the script:

```bash
gcc -O2 -Wall -std=gnu99 -fopenmp -o bin/seq   src/array.c src/sequential.c
gcc -O2 -Wall -std=gnu99 -fopenmp -o bin/omp   src/array.c src/omp.c
gcc -O2 -Wall -std=gnu99 -fopenmp -pthread -o bin/thread2 src/array.c src/thread2.c
mpicc -O2 -Wall -std=gnu99 -fopenmp -o bin/mpi src/array.c src/mpi.c
```

---

## Benchmark Results

All times are wall-clock (`real`), measured with POSIX `time`, single run per configuration. MPI was run with `mpirun -np 4`.

### Matrix Multiplication

![Matrix multiplication runtime vs input size, log scale, across Sequential, OpenMP, Pthreads, and MPI](assets/matrix_multiplication_runtime.png)

| Size | Sequential | OpenMP | Pthreads | MPI (4p) |
|---|---|---|---|---|
| 5×4 | 0.006s | 0.014s | 0.007s | 0.081s |
| 10×10 | 0.004s | 0.007s | 0.004s | 0.079s |
| 500×500 | 1.011s | 0.785s | 0.758s | 0.071s |
| 2000×2000 | 1m 46.573s | 54.399s | 57.713s | 0.094s¹ |
| 5000×5000 | 37m 52.786s | 22m 48.886s | 19m 49.032s | 0.247s¹ |

¹ These MPI timings are faster than the arithmetic workload would predict at scale, measured from a single run and not re-verified against sequential output for correctness. See [Notes & Caveats](#notes--caveats).

### Merge Sort

![Merge sort runtime vs input size, log scale, across Sequential, OpenMP, Pthreads, and MPI](assets/merge_sort_runtime.png)

| Array size | Sequential | OpenMP | Pthreads | MPI (4p) |
|---|---|---|---|---|
| 5 | 0.004s | 0.006s | 0.005s | 0.190s |
| 10 | 0.004s | 0.015s | 0.005s | 0.070s |
| 500 | 0.004s | 0.006s | 0.004s | 0.071s |
| 2000 | 0.007s | 0.014s | 0.008s | 0.077s |
| 5000 | 0.010s | 0.011s | 0.008s | 0.094s |
| 500000 | 0.327s | 0.246s | 0.176s | 0.061s |

**Reading the tables:** at small sizes, every parallel model is *slower* than sequential — thread/process setup cost exceeds the actual work. Pthreads consistently overtakes OpenMP once arrays/matrices are large enough for coarse, well-balanced partitioning to pay off. MPI only becomes competitive once per-process computation is large relative to the fixed cost of scatter/gather.

<details>
<summary>Raw terminal output (click to expand)</summary>

```
* * * * * * * 500x500 Matrix
with sequential     0m1.011s
with omp             0m0.785s
with thread2         0m0.758s
with mpi(4p)         0m0.071s

* * * * * * * Array size 500000
with sequential      0m0.327s
with omp              0m0.246s
with thread2          0m0.176s
with mpi(4p)          0m0.061s
```

Full logs for every input size are in the [written report (PDF)](./report.pdf).

</details>

---

## Notes & Caveats

- The MPI results for `2000×2000` and `5000×5000` matrices (0.094s and 0.247s) are notably fast relative to the sequential baseline (106s and 2273s) for a 4-process run of an O(n³) compute-bound workload. They are reported as measured, but have not been re-verified by diffing MPI output against the sequential result — that verification is a planned follow-up before treating this as a confirmed scaling result.
- Benchmarks are single-run wall-clock measurements, not averaged over multiple trials, so figures should be read as indicative trends rather than statistically rigorous measurements.
- All models were compiled with `-O2`; no workload-specific compiler tuning was applied, to keep the comparison focused on the parallelization strategy itself.

---

## Tech Stack

`C (gnu99)` · `OpenMP` · `POSIX Threads` · `MPI (OpenMPI)` · `Python 3` (test data generation) · `Bash` (automation) · `GNU Make`

---

## Author

**Namra Basharat**
BS Bioinformatics, National University of Sciences and Technology (NUST)
Operating Systems

## Acknowledgments

Matrix multiplication scaffold adapted from [mperlet/matrix_multiplication](https://github.com/mperlet/matrix_multiplication); Python generator and benchmarking script were rewritten for Python 3 and extended with additional input sizes and automated file-existence checks.

## License

[MIT](./LICENSE)
