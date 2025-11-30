#include <stdio.h>
#include <stdlib.h>
#include "array.h"

// Merge two sorted sections
static void merge(int *arr, int l, int m, int r) {
    int n1 = m - l + 1;
    int n2 = r - m;

    int *L = malloc(n1 * sizeof(int));
    int *R = malloc(n2 * sizeof(int));
    if(!L || !R){
        fprintf(stderr, "malloc failed\n");
        exit(EXIT_FAILURE);
    }

    for(int i = 0; i < n1; i++) L[i] = arr[l + i];
    for(int j = 0; j < n2; j++) R[j] = arr[m + 1 + j];

    int i = 0, j = 0, k = l;
    while(i < n1 && j < n2)
        arr[k++] = (L[i] <= R[j]) ? L[i++] : R[j++];

    while(i < n1) arr[k++] = L[i++];
    while(j < n2) arr[k++] = R[j++];

    free(L);
    free(R);
}

static void merge_sort(int *arr, int l, int r) {
    if(l >= r) return;

    int m = l + (r - l) / 2;
    merge_sort(arr, l, m);
    merge_sort(arr, m + 1, r);
    merge(arr, l, m, r);
}

int main(int argc, char **argv) {
    if(argc != 2) {
        printf("Provide one input file.\n");
        exit(EXIT_FAILURE);
    }
    array_struct *arr = get_array_struct(argv[1]);

    merge_sort(arr->data, 0, arr->size - 1);

    print_array(arr);
    free_array(arr);
    return 0;
}
