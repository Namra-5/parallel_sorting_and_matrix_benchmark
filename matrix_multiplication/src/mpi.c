#include <stdio.h>
#include <stdlib.h>
#include <mpi.h>
#include <string.h>
#include "matrix.h"
#include "bench_common.h"

double *mat_2D_to_1D(matrix_struct *m) {
    double *matrix = malloc( (size_t)m->rows * m->cols * sizeof(double) );
    if (matrix == NULL) {
        fprintf(stderr, "Error: out of memory.\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    for (int i = 0; i < m->rows; i++) {
        memcpy( matrix + ((size_t)i * m->cols), m->mat_data[i], m->cols * sizeof(double) );
    }
    return matrix;
}

int main(int argc, char *argv[]) {
    /** Matrix Properties
     * [0] = Rows of Matrix A
     * [1] = Cols of Matrix A
     * [2] = Rows of Matrix B
     * [3] = Cols of Matrix B
     **/
    int matrix_properties[4] = {0, 0, 0, 0};
     
    double *m_a = NULL;
    double *m_b = NULL;
    double *final_matrix = NULL;
    
    int num_worker, rank;

    MPI_Init(&argc, &argv);
    MPI_Comm_size(MPI_COMM_WORLD, &num_worker);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    
    /** the master initializes the data **/
    if (rank == 0) {
        
        if(argc != 3){
            fprintf(stderr, "ERROR: Please specify exactly 2 files.\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
            
        matrix_struct *m_1 = get_matrix_struct(argv[1]);
        matrix_struct *m_2 = get_matrix_struct(argv[2]);

        if(m_1->cols != m_2->rows){
            fprintf(stderr, "ERROR: The number of columns of matrix A must match the number of rows of matrix B.\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        
        // fill the property-array for workers
        matrix_properties[0] = m_1->rows;
        matrix_properties[1] = m_1->cols;
        matrix_properties[2] = m_2->rows;
        matrix_properties[3] = m_2->cols;
        
        /* generate 1D matrices for workers 
         * m_a is the 1D Matrix of m_1 
         * m_b is the 1D Matrix of m_2 
        */
        m_a = mat_2D_to_1D(m_1);
        m_b = mat_2D_to_1D(m_2);

        free_matrix(m_1);
        free_matrix(m_2);
    }

    // send the matrix properties to the workers
    MPI_Bcast(&matrix_properties, 4, MPI_INT, 0, MPI_COMM_WORLD);

    // calculate the 1D-sizes of the matrices
    int size_a   = matrix_properties[0] * matrix_properties[1];
    int size_b   = matrix_properties[2] * matrix_properties[3];
    int cols_res = matrix_properties[3];
    int size_res = matrix_properties[0] * cols_res;
    
    // allocate memory for 1D-matrices
    if(rank == 0) {
        final_matrix = malloc( (size_res ? (size_t)size_res : 1) * sizeof(double) );
    } else {
        m_a = malloc( (size_a ? (size_t)size_a : 1) * sizeof(double) );
        m_b = malloc( (size_b ? (size_t)size_b : 1) * sizeof(double) );
    }

    // Row distribution for ANY number of ranks: the first (rows % ranks) ranks
    // get one extra row. (Upstream aborted unless rows % ranks == 0.)
    int *rcounts = malloc( num_worker * sizeof(int) );   // doubles per rank
    int *rdispls = malloc( num_worker * sizeof(int) );
    {
        int base = matrix_properties[0] / num_worker;
        int extra = matrix_properties[0] % num_worker;
        int row0 = 0;
        for (int r = 0; r < num_worker; r++) {
            int nrows = base + (r < extra ? 1 : 0);
            rcounts[r] = nrows * cols_res;
            rdispls[r] = row0 * cols_res;
            row0 += nrows;
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);   // timed region starts after the input is read
    double bench_t0 = MPI_Wtime();

    // send 1D matrices to workers
    MPI_Bcast(m_a, size_a , MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Bcast(m_b, size_b , MPI_DOUBLE, 0, MPI_COMM_WORLD);
    
    // calculate the start- and endrow (inclusive) for worker  
    int startrow = (cols_res > 0) ? rdispls[rank] / cols_res : 0;
    int nrows_mine = (cols_res > 0) ? rcounts[rank] / cols_res : 0;
    int endrow = startrow + nrows_mine - 1;
    
    /* calculate sub matrices */
    int number_of_elems = rcounts[rank];
    double *result_matrix = calloc(number_of_elems ? (size_t)number_of_elems : 1, sizeof(double));

    int position = 0;

    for (int i = startrow; i <= endrow; i++) {
        for (int j = 0; j < matrix_properties[3]; j++) {
            for (int k = 0; k < matrix_properties[2]; k++) {
                result_matrix[position] +=
                    m_a[ ((size_t)i * matrix_properties[1] + k) ] *
                    m_b[ ((size_t)k * matrix_properties[3] + j) ];
            }
            position++;
        }
    }
    
    free(m_a);
    free(m_b);
    
    /* collect the results */
    MPI_Gatherv(result_matrix, number_of_elems, MPI_DOUBLE,
                final_matrix, rcounts, rdispls, MPI_DOUBLE, 0, MPI_COMM_WORLD);

    /** The master presents the results on the console */
    if (rank == 0){
        bench_report(MPI_Wtime() - bench_t0);
        int size = size_res;
        int i = 0;
        while (i < size) {
            printf("%lf\t", final_matrix[i]);
            i++;
        
            if (i % matrix_properties[3] == 0)
                printf("\n");
        }
    }
    
    free(result_matrix);
    free(final_matrix);
    free(rcounts);
    free(rdispls);
    
    MPI_Finalize();
    exit(EXIT_SUCCESS);
}
