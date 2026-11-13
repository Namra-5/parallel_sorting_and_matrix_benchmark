#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "matrix.h"

matrix_struct *get_matrix_struct(char matrix[]) {
    matrix_struct *m = malloc(sizeof(matrix_struct));
    if(m == NULL) {
        fprintf(stderr, "Error: out of memory.\n");
        exit(EXIT_FAILURE);
    }
    m->rows = 0;
    m->cols = 0;
    FILE* myfile = fopen(matrix, "r");
    
    if(myfile == NULL) {
        fprintf(stderr, "Error: The file '%s' could not be opened.\n", matrix);
        exit(EXIT_FAILURE);
    }
    // get the rows and columns
    int ch = 0;
    int prev = '\n';   // last character seen (a file must end a row with '\n')
    int any = 0;       // file contains at least one character
    while ((ch = fgetc(myfile)) != EOF) {
        any = 1;
        
        // count the columns at the first line (looking for "\t")
        if(m->rows == 0 && ch == '\t')
            m->cols++;
        
        // count the rows with "\n"
        if(ch == '\n')
            m->rows++;

        prev = ch;
    }

    // a last row without a terminating newline still counts as a row
    // (it used to be dropped silently, producing a wrong result with exit code 0)
    if(any && prev != '\n')
        m->rows++;

    if(m->rows == 0) {
        fprintf(stderr, "Error: '%s' contains no matrix data.\n", matrix);
        exit(EXIT_FAILURE);
    }
    
    // write rows and cols to struct
    m->cols++;
    
    // allocate memory for matrix data
    m->mat_data = calloc(m->rows, sizeof(double*)); 
    int i;
    if(m->mat_data == NULL) {
        fprintf(stderr, "Error: out of memory.\n");
        exit(EXIT_FAILURE);
    }
    for(i=0; i < m->rows; ++i) {
        m->mat_data[i]=calloc(m->cols, sizeof(double));
        if(m->mat_data[i] == NULL) {
            fprintf(stderr, "Error: out of memory.\n");
            exit(EXIT_FAILURE);
        }
    }
        
    
    rewind(myfile);
    int x,y;
    
    // fill matrix with data
    for(x = 0; x < m->rows; x++) {
        for(y = 0; y < m->cols; y++) {
            // fscanf returns EOF (-1) at end of file, which "!fscanf" treated as
            // success: a truncated file silently became zeros.
            if (fscanf(myfile, "%lf", &m->mat_data[x][y]) != 1) {
                fprintf(stderr, "Error: '%s' is truncated or malformed (row %d, column %d).\n",
                        matrix, x + 1, y + 1);
                exit(EXIT_FAILURE);
            }
        }
    }
    
    fclose(myfile);

    return m;
}

void print_matrix(matrix_struct *matrix_to_print){
    int i,j;
    for(i = 0; i < matrix_to_print->rows; i++) {
        for(j = 0; j < matrix_to_print->cols; j++) {
            printf("%lf\t",matrix_to_print->mat_data[i][j]); //Use lf format specifier, \n is for new line
        }
        printf("\n");
    }
}

void free_matrix(matrix_struct *matrix_to_free) {
    for(int i = 0; i < matrix_to_free->rows; i++) {
        free(matrix_to_free->mat_data[i]);
    }
    free(matrix_to_free->mat_data);
    free(matrix_to_free);
}

