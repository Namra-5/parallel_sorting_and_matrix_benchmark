typedef struct {
    unsigned int size;
    int *data;
} array_struct;

array_struct* get_array_struct(char filename[]);
void print_array(array_struct *arr);
void free_array(array_struct *arr);
