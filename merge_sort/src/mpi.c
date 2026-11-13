#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include "array.h"
#include "msort.h"
#include "bench_common.h"

/* Distributed merge sort: Scatterv -> local msort_seq -> Gatherv -> merge on
 * rank 0. Uses Scatterv/Gatherv so ANY n works with ANY number of ranks (the
 * previous Scatter/Gather version required n % ranks == 0 and otherwise
 * returned a wrongly sorted array with exit code 0). */
int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    array_struct *input = NULL;
    int n = 0;
    if (rank == 0) {
        if (argc != 2) {
            fprintf(stderr, "Usage: %s <input-file>\n", argv[0]);
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        input = get_array_struct(argv[1]);
        n = (int)input->size;
    }
    MPI_Bcast(&n, 1, MPI_INT, 0, MPI_COMM_WORLD);

    int *counts = malloc((size_t)size * sizeof(int));
    int *displs = malloc((size_t)size * sizeof(int));
    int *bounds = malloc(((size_t)size + 1) * sizeof(int));
    if (!counts || !displs || !bounds)
        MPI_Abort(MPI_COMM_WORLD, 1);
    int base = n / size, extra = n % size, offset = 0;
    for (int i = 0; i < size; i++) {
        counts[i] = base + (i < extra ? 1 : 0);
        displs[i] = offset;
        offset += counts[i];
    }

    int mine = counts[rank];
    int *local = malloc((mine ? (size_t)mine : 1) * sizeof(int));
    int *tmp = malloc((rank == 0 ? (n ? (size_t)n : 1) : (mine ? (size_t)mine : 1)) * sizeof(int));
    int *sorted = (rank == 0) ? malloc((n ? (size_t)n : 1) * sizeof(int)) : NULL;
    if (!local || !tmp || (rank == 0 && !sorted))
        MPI_Abort(MPI_COMM_WORLD, 1);

    MPI_Barrier(MPI_COMM_WORLD);       /* timed region starts after input is read */
    double t0 = MPI_Wtime();

    MPI_Scatterv(rank == 0 ? input->data : NULL, counts, displs, MPI_INT,
                 local, mine, MPI_INT, 0, MPI_COMM_WORLD);
    msort_seq(local, tmp, 0, mine - 1);
    MPI_Gatherv(local, mine, MPI_INT,
                sorted, counts, displs, MPI_INT, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        for (int i = 0; i < size; i++)
            bounds[i] = displs[i];
        bounds[size] = n;
        msort_merge_runs(sorted, tmp, bounds, size);
        bench_report(MPI_Wtime() - t0);
        print_ints(sorted, (unsigned int)n);
        free(sorted);
        free_array(input);
    }

    free(local);
    free(tmp);
    free(bounds);
    free(displs);
    free(counts);
    MPI_Finalize();
    return 0;
}
