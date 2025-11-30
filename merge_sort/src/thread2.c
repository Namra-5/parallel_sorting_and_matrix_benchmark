#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include "array.h"

typedef struct {
    int *arr;
    int left;
    int right;
} thread_data;

static void merge(int *arr, int l, int m, int r){
    int n1 = m - l + 1;
    int n2 = r - m;

    int *L = malloc(n1 * sizeof(int));
    int *R = malloc(n2 * sizeof(int));

    for(int i=0; i<n1; i++) L[i] = arr[l+i];
    for(int i=0; i<n2; i++) R[i] = arr[m+1+i];

    int i=0,j=0,k=l;
    while(i<n1 && j<n2)
        arr[k++] = (L[i] <= R[j]) ? L[i++] : R[j++];

    while(i<n1) arr[k++] = L[i++];
    while(j<n2) arr[k++] = R[j++];

    free(L); free(R);
}

static void merge_sort_seq(int *arr, int l, int r){
    if(l >= r) return;

    int m = l + (r-l)/2;
    merge_sort_seq(arr, l, m);
    merge_sort_seq(arr, m+1, r);
    merge(arr, l, m, r);
}

static void *thread_sort(void *arg){
    thread_data *d = (thread_data*)arg;
    merge_sort_seq(d->arr, d->left, d->right);
    return NULL;
}

int main(int argc, char **argv){
    if(argc != 2){
        printf("Provide one input file.\n");
        exit(EXIT_FAILURE);
    }

    array_struct *arr = get_array_struct(argv[1]);

    int cores = sysconf(_SC_NPROCESSORS_ONLN);
    pthread_t *threads = malloc(cores * sizeof(pthread_t));
    thread_data *td = malloc(cores * sizeof(thread_data));

    int chunk = arr->size / cores;
    int start = 0;

    for(int i=0; i<cores; i++){
        td[i].arr = arr->data;
        td[i].left = start;

        td[i].right = (i == cores-1) ?
            arr->size - 1 :
            start + chunk - 1;

        pthread_create(&threads[i], NULL, thread_sort, &td[i]);
        start += chunk;
    }

    for(int i=0; i<cores; i++) pthread_join(threads[i], NULL);

    /*** Merge all chunks sequentially ***/
    int step = chunk;
    while(step < arr->size){
        int left = 0;
        while(left + step < arr->size){
            int mid = left + step -1;
            int right = (left + 2*step -1 < arr->size) ?
                        (left + 2*step -1) :
                        (arr->size-1);
            merge(arr->data, left, mid, right);
            left += 2*step;
        }
        step *= 2;
    }

    print_array(arr);
    free(threads);
    free(td);
    free_array(arr);
    return 0;
}
