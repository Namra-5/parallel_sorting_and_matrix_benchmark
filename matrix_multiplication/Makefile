# Matrix-multiplication benchmark binaries: bin/seq bin/omp bin/thread2 bin/mpi
#   make                  build everything (needs gcc with OpenMP and mpicc)
#   make sequential omp thread2   build only the non-MPI models
#   make clean
#   make EXTRA_CFLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"   (debug builds)
#
# macOS: Apple's `gcc` is clang without OpenMP. Install GCC (brew install gcc open-mpi)
# and call e.g.  make CC=gcc-14 MPICC=mpicc
CC      = gcc
MPICC  ?= mpicc
TUNE    = -O2
# -ffp-contract=off: no fused multiply-add, so every model (and every CPU/compiler)
# rounds identically and parallel output can be compared byte-for-byte with the
# sequential output.
CFLAGS  = -Wall -std=gnu99 -g -fopenmp -ffp-contract=off -I../common $(EXTRA_CFLAGS)
LIBS    = src/matrix.c
HDRS    = src/matrix.h ../common/bench_common.h

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
