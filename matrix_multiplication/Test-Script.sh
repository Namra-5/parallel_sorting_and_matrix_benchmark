#!/bin/bash
echo "generate test-matrices with python if no test data found"
echo

# ----------- 5x4 and 4x5 -----------
if [ ! -f data/mat_5_4.txt ]; then
    echo "generate 5x4 matrix..."
    python3 random_float_matrix.py 5 4 > data/mat_5_4.txt
fi

if [ ! -f data/mat_4_5.txt ]; then
    python3 random_float_matrix.py 4 5 > data/mat_4_5.txt

fi

# ----------- 10x10 -----------
if [ ! -f data/mat_10x10a.txt ]; then
    echo "generate 10x10 matrix A..."
    python3 random_float_matrix.py 10 10 > data/mat_10x10a.txt
fi

if [ ! -f data/mat_10x10b.txt ]; then
    echo "generate 10x10 matrix B..."
    python3 random_float_matrix.py 10 10 > data/mat_10x10b.txt
fi

# ----------- 500x500 -----------
if [ ! -f data/mat_500x500a.txt ]; then
    echo "generate 500x500 matrix A..."
    python3 random_float_matrix.py 500 500 > data/mat_500x500a.txt
fi

if [ ! -f data/mat_500x500b.txt ]; then
    echo "generate 500x500 matrix B..."
    python3 random_float_matrix.py 500 500 > data/mat_500x500b.txt
fi

# ----------- 2000x2000 -----------
if [ ! -f data/mat_2000x2000a.txt ]; then
    echo "generate 2000x2000 matrix A..."
    python3 random_float_matrix.py 2000 2000 > data/mat_2000x2000a.txt
fi

if [ ! -f data/mat_2000x2000b.txt ]; then
    echo "generate 2000x2000 matrix B..."
    python3 random_float_matrix.py 2000 2000 > data/mat_2000x2000b.txt

fi

# ----------- 5000x5000 -----------
if [ ! -f data/mat_5000x5000a.txt ]; then
    echo "generate 5000x5000 matrix..."
    python3 random_float_matrix.py 5000 5000 > data/mat_5000x5000a.txt
fi
if [ ! -f data/mat_5000x5000b.txt ]; then
    python3 random_float_matrix.py 5000 5000 > data/mat_5000x5000b.txt
fi

echo "compile..."
echo
make
echo
echo "calculate..."
echo
echo "* * * * * * * 5x4 Matrix"
cal_t=$( { time bin/seq data/mat_5_4.txt data/mat_4_5.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with sequential    $cal_t"

cal_t=$( { time bin/omp data/mat_5_4.txt data/mat_4_5.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with omp           $cal_t"

cal_t=$( { time bin/thread2 data/mat_5_4.txt data/mat_4_5.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with thread2       $cal_t"

cal_t=$( { time mpirun -np 4 bin/mpi data/mat_5_4.txt data/mat_4_5.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with mpi(4p)       $cal_t"
echo


echo "* * * * * * * 10x10 Matrix"
cal_t=$( { time bin/seq data/mat_10x10a.txt data/mat_10x10b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with sequential    $cal_t"

cal_t=$( { time bin/omp data/mat_10x10a.txt data/mat_10x10b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with omp           $cal_t"

cal_t=$( { time bin/thread2 data/mat_10x10a.txt data/mat_10x10b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with thread2       $cal_t"

cal_t=$( { time mpirun -np 4 bin/mpi data/mat_10x10a.txt data/mat_10x10b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with mpi(4p)       $cal_t"
echo


echo "* * * * * * * 500x500 Matrix"
cal_t=$( { time bin/seq data/mat_500x500a.txt data/mat_500x500b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with sequential    $cal_t"

cal_t=$( { time bin/omp data/mat_500x500a.txt data/mat_500x500b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with omp           $cal_t"

cal_t=$( { time bin/thread2 data/mat_500x500a.txt data/mat_500x500b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with thread2       $cal_t"

cal_t=$( { time mpirun -np 4 bin/mpi data/mat_500x500a.txt data/mat_500x500b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with mpi(4p)       $cal_t"
echo


echo "* * * * * * * 2000x2000 Matrix"
cal_t=$( { time bin/seq data/mat_2000x2000a.txt data/mat_2000x2000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with sequential    $cal_t"

cal_t=$( { time bin/omp data/mat_2000x2000a.txt data/mat_2000x2000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with omp           $cal_t"

cal_t=$( { time bin/thread2 data/mat_2000x2000a.txt data/mat_2000x2000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with thread2       $cal_t"

cal_t=$( { time mpirun -np 4 bin/mpi data/mat_2000x2000a.txt data/mat_2000x2000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with mpi(4p)       $cal_t"
echo


echo "* * * * * * * 5000x5000 Matrix"
cal_t=$( { time bin/seq data/mat_5000x5000a.txt data/mat_5000x5000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with sequential    $cal_t"

cal_t=$( { time bin/omp data/mat_5000x5000a.txt data/mat_5000x5000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with omp           $cal_t"

cal_t=$( { time bin/thread2 data/mat_5000x5000a.txt data/mat_5000x5000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with thread2       $cal_t"

cal_t=$( { time mpirun -np 4 bin/mpi data/mat_5000x5000a.txt data/mat_5000x5000b.txt > /dev/null; } 2>&1 | grep real | awk '{print $2}' )
echo "with mpi(4p)       $cal_t"
echo
