#!/bin/bash
echo "generate test-arrays with python if no test data found"
echo

if [ ! -f data/array_5.txt ]; then
    echo "generate array of size 5..."
    python3 random_array.py 5 > data/array_5.txt
fi

if [ ! -f data/array_10.txt ]; then
    echo "generate array of size 10..."
    python3 random_array.py 10 > data/array_10.txt
fi

if [ ! -f data/array_500.txt ]; then
    echo "generate array of size 500..."
    python3 random_array.py 500 > data/array_500.txt
fi

if [ ! -f data/array_2000.txt ]; then
    echo "generate array of size 2000..."
    python3 random_array.py 2000 > data/array_2000.txt
fi

if [ ! -f data/array_5000.txt ]; then
    echo "generate array of size 5000..."
    python3 random_array.py 5000 > data/array_5000.txt
fi

if [ ! -f data/array_500000.txt ]; then
    echo "generate array of size 500000..."
    python3 random_array.py 500000 > data/array_500000.txt
fi

echo "compile..."
make
echo
echo "calculate..."
echo

echo "* * * * * * * Array size 5"
cal_t=$((time bin/seq data/array_5.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_5.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_5.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_5.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo

echo "* * * * * * * Array size 10"
cal_t=$((time bin/seq data/array_10.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_10.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_10.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_10.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo

echo "* * * * * * * Array size 500"
cal_t=$((time bin/seq data/array_500.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_500.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_500.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_500.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo

echo "* * * * * * * Array size 2000"
cal_t=$((time bin/seq data/array_2000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_2000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_2000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_2000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo

echo "* * * * * * * Array size 5000"
cal_t=$((time bin/seq data/array_5000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_5000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_5000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_5000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo

echo "* * * * * * * Array size 500000"
cal_t=$((time bin/seq data/array_500000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with sequential    $cal_t"

cal_t=$((time bin/omp data/array_500000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with omp           $cal_t"

cal_t=$((time bin/thread2 data/array_500000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with thread2       $cal_t"

cal_t=$((time mpirun -np 4 bin/mpi data/array_500000.txt) 2>&1 > /dev/null | grep real | awk '{print $2}')
echo "with mpi(4p)       $cal_t"
echo
