#!/usr/bin/env bash
# Quick wall-clock timing of the four matrix-multiplication binaries (legacy convenience script).
#
# For validated, repeatable measurements (output checked against the sequential
# result, several repetitions, hardware recorded) use:
#     python3 ../benchmark/run_benchmark.py --workload matrix
#
# Unlike the original version of this script, a failed run is reported as FAILED
# instead of being timed: the old `time mpirun ... | grep real` pipeline hid the
# "not enough slots" error and printed the ~0.07 s a failed launch takes as if it
# were a result.
set -u
cd "$(dirname "$0")" || exit 1

MPI_NP=${MPI_NP:-4}
# rows x inner x cols of A(rows x inner) * B(inner x cols); the default list is the original one.
# 5000 needs ~40 minutes sequentially: drop it with e.g.  SIZES="500 2000" ./Test-Script.sh
SIZES=${SIZES:-"5x4 10 500 2000 5000"}

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
echo "generate test-matrices with python if no test data found"
# "5x4" means A is 5x4 and B is 4x5; a plain "N" means two NxN matrices.
for s in $SIZES; do
    case "$s" in
        *x*) r=${s%x*}; c=${s#*x}
             a="data/mat_${r}_${c}.txt"; b="data/mat_${c}_${r}.txt"
             [ -s "$a" ] || { echo "generate ${r}x${c} matrix..."; python3 random_float_matrix.py "$r" "$c" > "$a"; }
             [ -s "$b" ] || python3 random_float_matrix.py "$c" "$r" > "$b" ;;
        *)   a="data/mat_${s}x${s}a.txt"; b="data/mat_${s}x${s}b.txt"
             [ -s "$a" ] || { echo "generate ${s}x${s} matrix A..."; python3 random_float_matrix.py "$s" "$s" > "$a"; }
             [ -s "$b" ] || { echo "generate ${s}x${s} matrix B..."; python3 random_float_matrix.py "$s" "$s" > "$b"; } ;;
    esac
done

echo "compile..."
make || exit 1
echo
echo "calculate..."
for s in $SIZES; do
    case "$s" in
        *x*) r=${s%x*}; c=${s#*x}; a="data/mat_${r}_${c}.txt"; b="data/mat_${c}_${r}.txt"; label="${r}x${c}" ;;
        *)   a="data/mat_${s}x${s}a.txt"; b="data/mat_${s}x${s}b.txt"; label="${s}x${s}" ;;
    esac
    echo
    echo "* * * * * * * ${label} Matrix"
    timed sequential bin/seq "$a" "$b"
    timed omp        bin/omp "$a" "$b"
    timed thread2    bin/thread2 "$a" "$b"
    timed "mpi(${MPI_NP}p)" mpirun $mpi_flags -np "$MPI_NP" bin/mpi "$a" "$b"
done
