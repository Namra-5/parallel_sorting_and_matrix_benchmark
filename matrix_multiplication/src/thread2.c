#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "matrix.h"
#include "bench_common.h"
#include <pthread.h>

struct v {
    int id; /* thread index */
    int nthreads; // total number of threads
    matrix_struct *m_1; // Matrix A
    matrix_struct *m_2; // Matrix B
    matrix_struct *result_matrix; // Result Matrix
};

void *worker(void *param); /* the thread */

int main(int argc, char **argv)
{
    // thread count: $BENCH_THREADS if set, otherwise the number of online CPUs
    int number_of_proc = bench_thread_count();

    if(argc != 3){
        fprintf(stderr, "ERROR: Please specify exactly 2 files.\n");
        exit(EXIT_FAILURE);
    }
        
    matrix_struct *m_1 = get_matrix_struct(argv[1]);
    matrix_struct *m_2 = get_matrix_struct(argv[2]);

    if(m_1->cols != m_2->rows){
        fprintf(stderr, "ERROR: The number of columns of matrix A must match the number of rows of matrix B.\n");
        exit(EXIT_FAILURE);
    }

    // allocate result matrix memory
    matrix_struct *result_matrix = malloc(sizeof(matrix_struct));
    result_matrix->rows = m_1->rows;
    result_matrix->cols = m_2->cols;
    result_matrix->mat_data = calloc(result_matrix->rows, sizeof(double*)); 
    for(int i=0; i < result_matrix->rows; ++i)
        result_matrix->mat_data[i]=calloc(result_matrix->cols, sizeof(double));

    // Allocate thread handles and per-thread parameters
    pthread_t *threads = malloc(number_of_proc * sizeof(pthread_t));
    struct v *data = malloc(number_of_proc * sizeof(struct v));

    double bench_t0 = bench_now();

    // thread creating loop
    for (int i = 0; i < number_of_proc; i++) {
        
        // fill the struct for thread worker
        data[i].id = i;
        data[i].nthreads = number_of_proc;
        data[i].m_1 = m_1;
        data[i].m_2 = m_2;
        data[i].result_matrix = result_matrix;
        
        // create thread
        if (pthread_create(&threads[i], NULL, worker, &data[i]) != 0) {
            fprintf(stderr, "ERROR: pthread_create failed for thread %d.\n", i);
            exit(EXIT_FAILURE);
        }
    }

    // join all threads
    for (int i = 0; i < number_of_proc; i++) {
        pthread_join(threads[i], NULL);
    }

    bench_report(bench_now() - bench_t0);

    print_matrix(result_matrix);
    
    free(threads);
    free(data);
    free_matrix(m_1);
    free_matrix(m_2);
    free_matrix(result_matrix);
    
    exit(EXIT_SUCCESS);
}

void *worker(void *param) {
    
    // struct with matrix data
    struct v *data = param;

    // balanced row split: every row is covered exactly once and thread loads
    // differ by at most one row (the old split gave the remainder to the last
    // thread, and ran everything on one thread when rows < threads)
    long long rows = data->result_matrix->rows;
    int startrow = (int)(rows * data->id / data->nthreads);
    int endrow   = (int)(rows * (data->id + 1) / data->nthreads);

    // calculate the matrix part from startrow to endrow
    for (int i = startrow; i < endrow; i++) {
        for (int j = 0; j < data->result_matrix->cols; j++) {
            for (int k = 0; k < data->m_2->rows; k++) {
                data->result_matrix->mat_data[i][j] += data->m_1->mat_data[i][k] * data->m_2->mat_data[k][j];
            }
        }
    }
    
    return NULL;
}
