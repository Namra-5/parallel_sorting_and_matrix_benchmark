# Benchmark tooling and dataset guide

## Pipeline

```
run_benchmark.py  -->  results/raw_runs.csv  ----\
                       results/hardware_environment.json
                       results/inputs_manifest.json   standardize.py --> results/benchmark_results.csv --> plot_results.py
```

```bash
python benchmark/run_benchmark.py --smoke                       # seconds; what CI runs (writes benchmark/results_smoke/)
python benchmark/run_benchmark.py --workload both --matrix-sizes 500 1000 2000 --sort-sizes 50000 500000 5000000 --reps 5 \
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
| wall_s | whole-process seconds (includes `mpirun` start-up, input parsing, printing) |
| kernel_s | in-program seconds (computation only; MPI also scatter/gather/merge); empty if unavailable |
| exit_code, output_sha256_16, status, stderr_head | validation data (first 16 hex chars of SHA-256; first 160 chars of stderr) |

## `benchmark_results.csv` (one row per configuration)

| column | meaning |
|---|---|
| n_runs, n_ok, n_failed, n_mismatch, n_timeout, n_no_reference | repetition accounting |
| median_s, mean_s, std_s, min_s, max_s | wall time over **valid** runs |
| kernel_median_s | median in-program time over valid runs |
| seq_median_s | sequential wall median for the **same workload and size** |
| speedup_vs_seq, efficiency | `T_seq / T_N`, and that divided by N |
| speedup_vs_1worker, efficiency_vs_1worker | same model with one worker as baseline |
| kernel_speedup_vs_seq, kernel_efficiency, kernel_speedup_vs_1worker | the same from kernel time |
| status | `ok` all runs valid · `PARTIAL` some invalid · `INVALID` none valid |
| scaling_valid | not INVALID **and** not oversubscribed: select these rows for scaling claims |

## `hardware_environment.json`
OS, CPU model, usable logical CPUs, physical cores, container CPU quota, effective cores, governor, memory, `gcc` and
`mpirun` versions, MPI flavour, the compiler flags read from each Makefile, the data seed, the git commit (and whether the
tree was dirty), and your `--notes`. Always publish it next to the results.

## Reading results correctly
- `wall_s` includes serial input parsing, so it caps speedup (Amdahl). Use `kernel_*` columns for the scaling behaviour of
  the algorithm and `wall_*` for end-to-end behaviour.
- MPI on one node measures process-level parallelism over shared memory, not network scaling. `mpirun` start-up is a
  fixed cost of several tenths of a second on small machines; it is part of `wall_s` and absent from `kernel_s`.
- Hyper-threads do not count as cores: an 8-thread run on a 4-core/8-thread CPU is flagged oversubscribed.
- `legacy_single_run_results.csv` holds the 2025 README tables (all MPI rows flagged); it is provenance, not data to cite.
