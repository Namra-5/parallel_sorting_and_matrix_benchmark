# Operating System Assignment 4 

##### Parallel Computing: Merge Sort & Matrix Multiplication Benchmark 

----------

This project implements two computational workloads using multiple execution models:

1. **Merge Sort**  
2. **Matrix Multiplication**  

Each workload is implemented in four variants:

* Sequential execution
* OpenMP shared-memory execution
* Explicitly threaded execution using Pthreads
* Message Passing execution using MPI

The main goal is to explore parallelism, measure performance improvements, and understand the trade-offs of different parallel programming paradigms.

---

## Execution Models

| Model | Type | Memory | Key Points |
|-------|------|--------|------------|
| Sequential | Baseline | Single-threaded | Reference implementation for correctness. Minimal overhead. |
| OpenMP | Shared-memory | Threads | High-level, pragma-based parallelism. Automatic scheduling. |
| POSIX Threads (Pthreads) | Shared-memory | Threads | Low-level control over workload partitioning and synchronization. |
| MPI | Distributed-memory | Processes | Scalable across nodes. Communication dominates small workloads. |

> Parallelism improves runtime only when the **amount of useful work offsets concurrency management costs**.

---

## Merge Sort
Merge Sort is a divide-and-conquer sorting algorithm. Arrays are recursively split into smaller subarrays, sorted individually, and then merged. The merging step can be parallelized because subarrays are independent.  

---

## Matrix Multiplication
The task is to multiply two matrices. To do this correctly, the number of columns in the first matrix must match the number of rows in the second matrix. Each element of the result matrix is independent, making the multiplication highly parallelizable.  

---

## Project Tree
    .
    |-- merge_sort
    | |-- bin
    | | |-- mpi
    | | |-- omp
    | | |-- seq
    | | `-- thread2 
    | |-- data 
    | | |-- array_10.txt
    │ │ |-- array_2000.txt
    │ │ |-- array_5.txt
    │ │ |-- array_500.txt
    │ │ |-- array_5000.txt
    │ │ `-- array_500000.txt
    | |-- src
    | | |-- array.c
    | | |-- array.h
    | | |-- sequential.c
    | | |-- omp.c
    | | |-- thread2.c
    | | `-- mpi.c 
    | |-- Makefile 
    | |-- random_array.py 
    | `-- Test-Script.sh
    |-- matrix_multiplication
    | |-- bin
    | | |-- mpi
    | | |-- omp
    | | |-- seq
    | | `-- thread2 
    | |-- data 
    | | |-- mat_4_5.txt 
    | | |-- mat_5_4.txt 
    | | |-- mat_10x10a.txt
    | | |-- mat_10x10b.txt
    | | |-- mat_2000x2000a.txt
    | | |-- mat_2000x2000b.txt
    | | |-- mat_5000x5000a.txt
    | | |-- mat_5000x5000b.txt
    | | |-- mat_500x500a.txt
    | | `-- mat_500x500b.txt
    | |-- src
    | | |-- matrix.c
    | | |-- matrix.h
    | | |-- mpi.c
    | | |-- omp.c
    | | |-- sequential.c
    | | |-- thread.c
    | | `-- thread2.c 
    | |-- Makefile 
    | |-- random_float_matrix.py 
    | `-- Test-Script.sh
    |-- README.md
    `-- LICENSE

---

## Experimental Setup

- All models compiled with GCC/MPICC using appropriate flags in Makefile.
- Random input datasets generated using Python scripts.
- Execution times measured with POSIX `time` utility (`real` metric).
- Only computational runtime is measured; printing and debugging outputs are suppressed.

---

## Compilation

 The Makefile automates compilation for all implementations using the `make` command. The resulting binaries are stored in the `bin/` directory.
 
 ---

## Merge Sort Implementation

- **Sequential:** Classical recursive divide-and-conquer merge sort. Serves as baseline.
- **OpenMP:** Parallelizes recursive calls using tasks. Maximum recursion depth limited to available threads.
- **Pthreads:** Explicit slice partitioning. Each thread sorts its subarray, followed by a bottom-up merge.
- **MPI:** Distributes array segments across processes. Each process sorts locally; master gathers and merges.

### Running Merge Sort

```bash
cd merge_sort
chmod +x Test-Script.sh
./Test-Script.sh
```

---

## Matrix Multiplication Implementation

- **Sequential:** Standard triple-loop matrix multiplication. Complexity: O(n³).
- **OpenMP:** Parallelizes outer loops using shared-memory threads.
- **Pthreads:** Explicit block-based partitioning. Each thread multiplies assigned submatrix.
- **MPI:** Distributed block multiplication. Data is scattered to processes and gathered back after local computations.

### Running Matrix Multiplication

```bash
cd matrix_multiplication
chmod +x Test-Script.sh
./Test-Script.sh
```

---

## Performance Observations

The following observations summarize the runtime behavior across different input sizes and execution models.

- **Small inputs:** Sequential execution is fastest due to minimal overhead. Parallel models (OpenMP, Pthreads, MPI) incur thread/process creation and synchronization costs that dominate computation for tiny workloads.
- **Medium inputs:** Shared-memory models (OpenMP, Pthreads) provide noticeable speedup. Thread-based parallelism becomes worthwhile as subproblems grow larger.
- **Large inputs:** MPI exhibits the best scalability. Distributed computation dominates communication overhead, making it suitable for very large datasets.
- **Overheads:** Thread and process management, as well as memory contention in shared-memory models, limit speedup for small to medium inputs.

> Selecting the appropriate execution model depends on **input size, workload distribution, and available hardware resources**.

---
