#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include "array.h"
#include "msort.h"
#include "bench_common.h"

typedef struct {
    int *arr;
    int *tmp;
    int left;
    int right;      /* inclusive; right < left means "nothing to do" */
} thread_data;

static void *thread_sort(void *arg)
{
    thread_data *d = arg;
    msort_seq(d->arr, d->tmp, d->left, d->right);
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <input-file>\n", argv[0]);
        return EXIT_FAILURE;
    }
    array_struct *arr = get_array_struct(argv[1]);
    int n = (int)arr->size;

    /* Never start more threads than there are elements (the old code divided
     * by zero-sized chunks and hung for n < cores). */
    int nthreads = bench_thread_count();
    if (nthreads > n) nthreads = n;
    if (nthreads < 1) nthreads = 1;

    int *tmp = malloc((n ? (size_t)n : 1) * sizeof(int));
    pthread_t *threads = malloc((size_t)nthreads * sizeof(pthread_t));
    thread_data *td = malloc((size_t)nthreads * sizeof(thread_data));
    int *bounds = malloc(((size_t)nthreads + 1) * sizeof(int));
    if (!tmp || !threads || !td || !bounds) {
        fprintf(stderr, "Error: out of memory.\n");
        return EXIT_FAILURE;
    }

    /* balanced split: the first n % nthreads chunks get one extra element */
    int base = n / nthreads, extra = n % nthreads, start = 0;
    for (int i = 0; i < nthreads; i++) {
        int len = base + (i < extra ? 1 : 0);
        bounds[i] = start;
        td[i].arr = arr->data;
        td[i].tmp = tmp;
        td[i].left = start;
        td[i].right = start + len - 1;
        start += len;
    }
    bounds[nthreads] = n;

    double t0 = bench_now();
    for (int i = 0; i < nthreads; i++) {
        if (pthread_create(&threads[i], NULL, thread_sort, &td[i]) != 0) {
            fprintf(stderr, "Error: pthread_create failed for thread %d.\n", i);
            return EXIT_FAILURE;
        }
    }
    for (int i = 0; i < nthreads; i++)
        pthread_join(threads[i], NULL);

    /* the merge of the per-thread runs is intentionally sequential */
    msort_merge_runs(arr->data, tmp, bounds, nthreads);
    bench_report(bench_now() - t0);

    print_array(arr);
    free(bounds);
    free(td);
    free(threads);
    free(tmp);
    free_array(arr);
    return 0;
}
