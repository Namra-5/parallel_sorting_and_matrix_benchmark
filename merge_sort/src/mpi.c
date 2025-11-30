#include <stdio.h>
#include <stdlib.h>
#include <mpi.h>
#include "array.h"

static void merge(int *arr,int l,int m,int r){
    int n1 = m-l+1;
    int n2 = r-m;
    int *L = malloc(n1*sizeof(int));
    int *R = malloc(n2*sizeof(int));
    for(int i=0;i<n1;i++) L[i]=arr[l+i];
    for(int i=0;i<n2;i++) R[i]=arr[m+1+i];
    int i=0,j=0,k=l;
    while(i<n1 && j<n2)
        arr[k++] = (L[i]<=R[j])?L[i++]:R[j++];
    while(i<n1) arr[k++] = L[i++];
    while(j<n2) arr[k++] = R[j++];
    free(L); free(R);
}

static void merge_sort_seq(int *arr,int l,int r){
    if(l >= r) return;
    int m = l + (r-l)/2;
    merge_sort_seq(arr,l,m);
    merge_sort_seq(arr,m+1,r);
    merge(arr,l,m,r);
}

int main(int argc,char **argv){
    MPI_Init(&argc,&argv);
    int rank,size;
    MPI_Comm_rank(MPI_COMM_WORLD,&rank);
    MPI_Comm_size(MPI_COMM_WORLD,&size);

    int *arr=NULL;
    int n=0;

    if(rank==0){
        if(argc!=2){
            printf("Provide one input file.\n");
            MPI_Abort(MPI_COMM_WORLD,1);
        }
        array_struct *a = get_array_struct(argv[1]);
        arr = a->data;
        n = a->size;
    }

    MPI_Bcast(&n,1,MPI_INT,0,MPI_COMM_WORLD);

    int chunk = (n + size - 1) / size;

    int *local = malloc(chunk*sizeof(int));

    MPI_Scatter(arr,chunk,MPI_INT,local,chunk,MPI_INT,0,MPI_COMM_WORLD);

    merge_sort_seq(local,0,chunk-1);

    int *sorted=NULL;
    if(rank==0) sorted = malloc(chunk*size*sizeof(int));

    MPI_Gather(local,chunk,MPI_INT,sorted,chunk,MPI_INT,0,MPI_COMM_WORLD);

    if(rank==0){
        int real=n;
        while(chunk < real){
            int left = 0;
            while(left + chunk < real){
                int mid = left + chunk -1;
                int right =
                    (left + 2*chunk -1 < real)?
                    (left + 2*chunk -1):
                    (real-1);
                merge(sorted,left,mid,right);
                left += 2*chunk;
            }
            chunk*=2;
        }
        for(int i=0;i<n;i++) printf("%d\t",sorted[i]);
        printf("\n");
        free(sorted);
        free(arr);
    }

    free(local);
    MPI_Finalize();
    return 0;
}
