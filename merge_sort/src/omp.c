#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#include "array.h"
#include "msort.h"
#include "bench_common.h"

/* Task-based parallel merge sort.
 *
 * The previous version used nested `#pragma omp parallel sections`. OpenMP
 * runtimes (libgomp included) default to ONE active parallel level, so every
 * nested region silently ran on a team of one thread and the "OpenMP" sort was
 * effectively sequential regardless of OMP_NUM_THREADS. Tasks need no nested
 * parallelism and balance themselves across the team.
 *
 * Ranges smaller than `cutoff` are sorted sequentially to bound task overhead. */
static void msort_tasks(int *a, int *tmp, int l, int r, int cutoff)
{
    if (l >= r)
        return;
    if (r - l + 1 <= cutoff) {
        msort_seq(a, tmp, l, r);
        return;
    }
    int m = l + (r - l) / 2;
    #pragma omp task firstprivate(a, tmp, l, m, cutoff)
    msort_tasks(a, tmp, l, m, cutoff);
    msort_tasks(a, tmp, m + 1, r, cutoff);
    #pragma omp taskwait
    msort_merge(a, tmp, l, m, r);
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <input-file>\n", argv[0]);
        return EXIT_FAILURE;
    }
    array_struct *arr = get_array_struct(argv[1]);
    int n = (int)arr->size;
    int *tmp = malloc((n ? (size_t)n : 1) * sizeof(int));
    if (!tmp) {
        fprintf(stderr, "Error: out of memory.\n");
        return EXIT_FAILURE;
    }

    int threads = omp_get_max_threads();
    int cutoff = n / (8 * threads);   /* roughly 8 leaf tasks per thread */
    if (cutoff < 512)
        cutoff = 512;

    double t0 = bench_now();
    #pragma omp parallel
    {
        #pragma omp single
        msort_tasks(arr->data, tmp, 0, n - 1, cutoff);
    }
    bench_report(bench_now() - t0);

    print_array(arr);
    free(tmp);
    free_array(arr);
    return 0;
}
