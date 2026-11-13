#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include "array.h"

array_struct *get_array_struct(const char *filename)
{
    FILE *f = fopen(filename, "r");
    if (!f) {
        fprintf(stderr, "Error: cannot open '%s'.\n", filename);
        exit(EXIT_FAILURE);
    }

    array_struct *arr = malloc(sizeof *arr);
    if (!arr) {
        fprintf(stderr, "Error: out of memory.\n");
        exit(EXIT_FAILURE);
    }
    arr->size = 0;

    /* pass 1: count the integers */
    int val;
    while (fscanf(f, "%d", &val) == 1) {
        if (arr->size == (unsigned int)INT_MAX) {
            fprintf(stderr, "Error: more than %d elements are not supported.\n", INT_MAX);
            exit(EXIT_FAILURE);
        }
        arr->size++;
    }
    if (!feof(f)) {                   /* stopped on a non-integer token */
        fprintf(stderr, "Error: '%s' contains a token that is not an integer "
                        "(after %u valid values).\n", filename, arr->size);
        exit(EXIT_FAILURE);
    }
    rewind(f);

    /* malloc(0) may return NULL, so always allocate at least one int */
    arr->data = malloc(((size_t)arr->size ? (size_t)arr->size : 1) * sizeof(int));
    if (!arr->data) {
        fprintf(stderr, "Error: out of memory.\n");
        exit(EXIT_FAILURE);
    }
    for (unsigned int i = 0; i < arr->size; i++) {
        if (fscanf(f, "%d", &arr->data[i]) != 1) {
            fprintf(stderr, "Error reading element %u from file.\n", i);
            exit(EXIT_FAILURE);
        }
    }
    fclose(f);
    return arr;
}

void print_ints(const int *data, unsigned int n)
{
    for (unsigned int i = 0; i < n; i++)
        printf("%d\t", data[i]);
    printf("\n");
}

void print_array(const array_struct *arr)
{
    print_ints(arr->data, arr->size);
}

void free_array(array_struct *arr)
{
    free(arr->data);
    free(arr);
}
