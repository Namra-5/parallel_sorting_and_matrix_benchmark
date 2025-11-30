CC = gcc
CFLAGS = -Wall -std=gnu99 -g -fopenmp
LIBS = src/array.c
TUNE = -O2

all: sequential omp thread2 mpi

sequential:
	$(CC) $(TUNE) $(CFLAGS) -o bin/seq $(LIBS) src/sequential.c

omp:
	$(CC) $(TUNE) $(CFLAGS) -o bin/omp $(LIBS) src/omp.c

thread2:
	$(CC) $(TUNE) $(CFLAGS) -pthread -o bin/thread2 $(LIBS) src/thread2.c

mpi:
	mpicc $(TUNE) $(CFLAGS) -o bin/mpi $(LIBS) src/mpi.c


