# Benchmark tooling and dataset guide

## Pipeline

```
run_benchmark.py  -->  results/raw_runs.csv  ----\
                       results/hardware_environment.json
                       results/inputs_manifest.json   standardize.py --> results/benchmark_results.csv --> plot_results.py
```

```bash
python benchmark/run_benchmark.py --smoke                       # seconds; what CI runs (writes benchmark/results_smoke/ locally)
python benchmark/run_benchmark.py --workload both --matrix-sizes 500 1000 1500 --sort-sizes 50000 500000 5000000 \
       --workers 1 2 3 4 --reps 5 --sort-reps 15 --cooldown 20 --warmup \
       --notes "bare metal, Ubuntu 24.04, performance governor, idle machine"
python benchmark/standardize.py
python benchmark/plot_results.py
```
Use `--workers 1 2 4 8` to choose worker counts (default: powers of two up to the physical cores, plus the core count).
The 5000×5000 matrix takes ≈ 38 min sequentially on the original machine; run it deliberately
(`--matrix-sizes 5000 --reps 1`). `raw_runs.csv` is written after every run, so an interrupted run keeps its data.
The harness exits with status 1 if any run is not `ok` (`--allow-failures` to override).

## How a run is judged (`status` in raw_runs.csv)

| status | meaning |
|---|---|
| `ok` | exit code 0 **and** SHA-256 of stdout equals the sequential output for the same input |
| `failed` | non-zero exit code (crash, MPI launch failure, bad input) |
| `mismatch` | exit 0 but different output than sequential: a wrong answer |
| `timeout` | exceeded `--timeout`; whole process tree killed |
| `no_reference` | the sequential run for this input failed, so nothing can be verified |

Only `ok` rows enter `benchmark_results.csv`.

## `raw_runs.csv` (one row per run)

| column | meaning |
|---|---|
| workload, model, size | `matrix`/`mergesort`; `seq`/`omp`/`thread2`/`mpi`; matrix side n (n×n) or array length |
| workers | OpenMP threads / Pthreads threads / MPI ranks (1 for `seq`) |
| oversubscribed | workers > effective cores (physical cores, capped by affinity and container CPU quota) |
| rep | repetition number |
| order | position of this run inside its repetition (1 = first); the order is shuffled with a seed, see the protocol below |
| start_utc, load1 | UTC start time of the run and the 1-minute load average just before it (background-load indicator) |
| wall_s | whole-process seconds (includes `mpirun` start-up, input parsing, printing) |
| kernel_s | in-program seconds (computation only; MPI also scatter/gather/merge); empty if unavailable |
| exit_code, output_sha256_16, status, stderr_head | validation data (first 16 hex chars of SHA-256; first 160 chars of stderr) |

## `benchmark_results.csv` (one row per configuration)

| column | meaning |
|---|---|
| n_runs, n_ok, n_failed, n_mismatch, n_timeout, n_no_reference | repetition accounting |
| median_s, mean_s, std_s, min_s, max_s | wall time over **valid** runs |
| kernel_median_s | median in-program time over valid runs |
| kernel_min_s, kernel_max_s | smallest and largest in-program time over the valid runs (the range drawn in the kernel-time figures) |
| kernel_std_s, kernel_cv | standard deviation and coefficient of variation (std / mean) of the in-program time: a noise indicator, large values (say above 0.15) mean the repetitions disagree |
| seq_median_s | sequential wall median for the **same workload and size** |
| speedup_vs_seq, efficiency | `T_seq / T_N`, and that divided by N |
| speedup_vs_1worker, efficiency_vs_1worker | same model with one worker as baseline |
| kernel_speedup_vs_seq, kernel_efficiency, kernel_speedup_vs_1worker | the same from kernel time |
| status | `ok` all runs valid · `PARTIAL` some invalid · `INVALID` none valid |
| scaling_valid | not INVALID **and** not oversubscribed: select these rows for scaling claims |

## `hardware_environment.json` fields

| field | meaning |
|---|---|
| schema_version | version of the record layout (currently 3) |
| collected_utc | UTC time at which the run started |
| os, python | platform string and Python version |
| cpu_model | CPU name from `lscpu` |
| logical_cpus_usable | CPUs the process may use (honours affinity/cpusets) |
| physical_cores | physical cores (SMT siblings counted once), capped by the usable CPUs |
| cgroup_cpu_limit | container CPU quota in cores, null if unlimited or unknown |
| effective_cores | cores a scaling experiment may use before it counts as oversubscribed (min of the two above and the quota) |
| cores_per_socket, threads_per_core | from `lscpu` |
| cpu_governor | Linux frequency governor, null if not readable (for example under WSL2) |
| memory_total_gib | installed memory |
| gcc, mpirun | first line of each tool's `--version` |
| mpi_flavor | informational label derived from the version text |
| mpi_launch_flags | `root` and `oversubscribe` flags found by test launches (`oversubscribe` is null if none worked) |
| cflags_matrix, cflags_mergesort | compiler flags parsed from each Makefile |
| data_seed | seed used for the input generators and for the run-order shuffle |
| protocol | `workers`, `reps`, `sort_reps`, `cooldown_s`, `warmup`, a note on the run order and on the reference run |
| git | `commit` and `dirty` (whether tracked files had uncommitted changes) of the code that ran |
| notes | free text given with `--notes` |

Always publish this file next to the results.

## Measurement protocol

For every (workload, size):

1. One untimed sequential run defines the expected output hash (it also warms the CPU and the page cache).
2. Each repetition runs every configuration once. **The order inside a repetition is shuffled** with a seed derived from the
   data seed, workload, size and repetition number; the position used is stored in `order`. A fixed order would make
   whichever configuration comes first after an idle pause systematically slower for millisecond-scale runs (CPU wake-up);
   in an earlier fixed-order run the sequential kernel at 50,000 elements was 63% slower than the identical one-thread
   OpenMP run that followed it, and showed no such effect at 50 ms and above.
3. `--warmup` runs the first scheduled configuration once, untimed, before each repetition; `--cooldown` pauses between
   repetitions (laptops throttle thermally); `--sort-reps` gives the cheap sorting workload more repetitions.

## Timed region (`kernel_s`)

Measured inside each program with a monotonic clock (`MPI_Wtime` for MPI); reading the input file and printing the result are
never included.

| program | starts | stops |
|---|---|---|
| sequential | before the multiplication / sort | after it |
| OpenMP | before the parallel region (so thread-team start-up is included) | after the parallel region |
| Pthreads | before the threads are created | after they are joined and the partial results merged |
| MPI | after an `MPI_Barrier` that follows the input being read on rank 0 | on rank 0 after the final gather (and, for sorting, the final merge); includes the broadcast/scatter of the data |

## Reading results correctly
- **Compare a model with itself.** `speedup_vs_1worker` / `kernel_speedup_vs_1worker` divide by the SAME model's one-worker
  time. `speedup_vs_seq` divides by the sequential binary, which is a different program (for example the MPI matrix code
  stores matrices in flat arrays, the others in arrays of row pointers), so it mixes implementation differences with
  parallelism.
- **Speedups above N are possible.** Splitting the data into smaller per-worker pieces can make them fit in cache, and short
  runs are noisy. Check `kernel_cv`, `min_s` and `max_s` before interpreting a value above N (cache behaviour is a hypothesis
  until it is measured with hardware counters).
- **Laptops drift.** Thermal throttling and background load change timings during long runs; repetitions are interleaved across
  models so all models are affected alike, and `--cooldown SECONDS` adds a pause between repetitions.
- `wall_s` includes serial input parsing, so it caps speedup (Amdahl). Use `kernel_*` columns for the scaling behaviour of
  the algorithm and `wall_*` for end-to-end behaviour.
- MPI on one node measures process-level parallelism over shared memory, not network scaling. `wall_s` of an MPI run also
  contains `mpirun` start-up (several tenths of a second) and the forwarding of the program's output through the launcher,
  which grows with output size; neither is in `kernel_s`. Prefer `kernel_*` columns when comparing MPI with the other models.
- Hyper-threads do not count as cores: an 8-thread run on a 4-core/8-thread CPU is flagged oversubscribed.
