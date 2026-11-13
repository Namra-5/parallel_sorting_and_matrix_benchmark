#ifndef ARRAY_H
#define ARRAY_H

typedef struct {
    unsigned int size;
    int *data;
} array_struct;

/* Read whitespace-separated integers. Exits with an error message on stderr if
 * the file cannot be opened or contains anything that is not an integer. */
array_struct *get_array_struct(const char *filename);
void print_ints(const int *data, unsigned int n);   /* "%d\t" per element, then "\n" */
void print_array(const array_struct *arr);
void free_array(array_struct *arr);

#endif
