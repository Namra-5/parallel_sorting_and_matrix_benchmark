# Merge-sort benchmark binaries: bin/seq bin/omp bin/thread2 bin/mpi
#   make                  build everything (needs gcc with OpenMP and mpicc)
#   make sequential omp thread2   build only the non-MPI models
#   make clean
#   make EXTRA_CFLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"   (debug builds)
CC      = gcc
MPICC  ?= mpicc
TUNE    = -O2
# -ffp-contract=off keeps floating-point rounding identical across models and
# compilers (no fused multiply-add differences); irrelevant for integer sorting
# but kept identical to the matrix Makefile so both workloads share one policy.
CFLAGS  = -Wall -std=gnu99 -g -fopenmp -ffp-contract=off -I../common $(EXTRA_CFLAGS)
LIBS    = src/array.c src/msort.c
HDRS    = src/array.h src/msort.h ../common/bench_common.h

.PHONY: all sequential omp thread2 mpi clean
all: sequential omp thread2 mpi

bin:
	mkdir -p bin

sequential: | bin
	$(CC) $(TUNE) $(CFLAGS) -o bin/seq $(LIBS) src/sequential.c

omp: | bin
	$(CC) $(TUNE) $(CFLAGS) -o bin/omp $(LIBS) src/omp.c

thread2: | bin
	$(CC) $(TUNE) $(CFLAGS) -pthread -o bin/thread2 $(LIBS) src/thread2.c

mpi: | bin
	$(MPICC) $(TUNE) $(CFLAGS) -o bin/mpi $(LIBS) src/mpi.c

clean:
	rm -f bin/seq bin/omp bin/thread2 bin/mpi
