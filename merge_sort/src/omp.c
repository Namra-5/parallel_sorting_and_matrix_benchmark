#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#include "array.h"

static void merge(int *arr,int l,int m,int r){
    int n1 = m-l+1;
    int n2 = r-m;

    int *L=malloc(n1*sizeof(int));
    int *R=malloc(n2*sizeof(int));

    for(int i=0;i<n1;i++) L[i]=arr[l+i];
    for(int i=0;i<n2;i++) R[i]=arr[m+1+i];

    int i=0,j=0,k=l;
    while(i<n1 && j<n2)
        arr[k++] = (L[i]<=R[j])?L[i++]:R[j++];

    while(i<n1) arr[k++]=L[i++];
    while(j<n2) arr[k++]=R[j++];

    free(L); free(R);
}

static void merge_sort_parallel(int *arr,int l,int r,int depth){
    if(l >= r) return;

    int m = l + (r - l) / 2;
    if(depth > 0) {
        #pragma omp parallel sections
        {
            #pragma omp section
            merge_sort_parallel(arr,l,m,depth-1);

            #pragma omp section
            merge_sort_parallel(arr,m+1,r,depth-1);
        }
    } else {
        merge_sort_parallel(arr,l,m,0);
        merge_sort_parallel(arr,m+1,r,0);
    }
    merge(arr,l,m,r);
}

int main(int argc,char **argv){
    if(argc!=2){
        printf("Provide one input file.\n");
        exit(EXIT_FAILURE);
    }
    array_struct *arr = get_array_struct(argv[1]);

    int threads = omp_get_max_threads();
    /** log2(threads) safe parallel depth **/
    int depth = 0;
    while((1<<depth) < threads) depth++;

    #pragma omp parallel
    {
        #pragma omp single nowait
        merge_sort_parallel(arr->data,0,arr->size-1,depth);
    }

    print_array(arr);
    free_array(arr);
    return 0;
}
