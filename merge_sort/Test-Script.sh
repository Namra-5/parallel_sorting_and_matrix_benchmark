#!/usr/bin/env bash
# Quick wall-clock timing of the four merge-sort binaries (legacy convenience script).
#
# For validated, repeatable measurements (output checked against the sequential
# result, several repetitions, hardware recorded) use:
#     python3 ../benchmark/run_benchmark.py --workload mergesort
#
# Unlike the original version of this script, a failed run is reported as FAILED
# instead of being timed: the old `time mpirun ... | grep real` pipeline hid the
# "not enough slots" error and printed the ~0.07 s a failed launch takes as if it
# were a result.
set -u
cd "$(dirname "$0")" || exit 1

MPI_NP=${MPI_NP:-4}
SIZES=${SIZES:-"5 10 500 2000 5000 500000"}

cores=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 1)
mpi_flags=""
if mpirun --version 2>&1 | grep -qi "open mpi"; then
    [ "$(id -u)" -eq 0 ] && mpi_flags="$mpi_flags --allow-run-as-root"
    [ "$MPI_NP" -gt "$cores" ] && mpi_flags="$mpi_flags --oversubscribe"
fi

# timed <label> <command...>: prints "with <label> <seconds>s" or FAILED (exit code, first stderr line)
timed() {
    local label=$1; shift
    local errf; errf=$(mktemp)
    local TIMEFORMAT=%R
    local t rc
    t=$( { time "$@" >/dev/null 2>"$errf"; echo $? >"$errf.rc"; } 2>&1 )
    rc=$(cat "$errf.rc")
    if [ "$rc" -eq 0 ]; then
        printf 'with %-14s %ss\n' "$label" "$t"
    else
        printf 'with %-14s FAILED (exit %s): %s\n' "$label" "$rc" "$(head -n 1 "$errf")"
    fi
    rm -f "$errf" "$errf.rc"
}

mkdir -p bin data
echo "generate test-arrays with python if no test data found"
for n in $SIZES; do
    [ -s "data/array_$n.txt" ] || { echo "generate array of size $n..."; python3 random_array.py "$n" > "data/array_$n.txt"; }
done

echo "compile..."
make || exit 1
echo
echo "calculate..."
for n in $SIZES; do
    f="data/array_$n.txt"
    echo
    echo "* * * * * * * Array size $n"
    timed sequential bin/seq "$f"
    timed omp        bin/omp "$f"
    timed thread2    bin/thread2 "$f"
    timed "mpi(${MPI_NP}p)" mpirun $mpi_flags -np "$MPI_NP" bin/mpi "$f"
done
