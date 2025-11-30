#include <stdio.h>
#include <stdlib.h>
#include "array.h"

array_struct* get_array_struct(char filename[]) {
    FILE *f = fopen(filename, "r");
    if(!f) { printf("Error opening file.\n"); exit(EXIT_FAILURE); }

    array_struct *arr = malloc(sizeof(array_struct));
    arr->size = 0;
    int val;

    // Count lines
    while(fscanf(f, "%d", &val) == 1) arr->size++;
    rewind(f);

    arr->data = malloc(arr->size * sizeof(int));
    for(unsigned int i = 0; i < arr->size; i++) {
    if (fscanf(f, "%d", &arr->data[i]) != 1) {
        fprintf(stderr, "Error reading element %u from file.\n", i);
        exit(EXIT_FAILURE);
    }
}
    fclose(f);
    return arr;
}

void print_array(array_struct *arr) {
    for(unsigned int i=0; i<arr->size; i++)
        printf("%d\t", arr->data[i]);
    printf("\n");
}

void free_array(array_struct *arr) {
    free(arr->data);
    free(arr);
}
