#include <stdio.h>
#include <stdlib.h>
#include "array.h"
#include "msort.h"
#include "bench_common.h"

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

    double t0 = bench_now();
    msort_seq(arr->data, tmp, 0, n - 1);
    bench_report(bench_now() - t0);

    print_array(arr);
    free(tmp);
    free_array(arr);
    return 0;
}
