/*
 * bench_common.h - tiny helpers shared by every benchmark binary.
 *
 *  bench_now()          monotonic wall clock in seconds (non-MPI models).
 *  bench_report(s)      if the environment variable BENCH_TIMING is set, print
 *                       "BENCH_KERNEL_S=<seconds>" to STDERR. stdout is never
 *                       touched, so the program's data output (which the Python
 *                       harness hashes and compares against the sequential
 *                       output) is identical with and without timing.
 *  bench_thread_count() number of worker threads for the Pthreads builds:
 *                       $BENCH_THREADS if set to a positive integer, otherwise
 *                       the number of online processors (the old behaviour).
 *
 * "Kernel time" covers the computation (plus, for MPI, scatter/gather and the
 * final merge) but NOT reading the input text file or printing the result.
 */
#ifndef BENCH_COMMON_H
#define BENCH_COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static inline double bench_now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static inline void bench_report(double seconds)
{
    if (getenv("BENCH_TIMING") != NULL)
        fprintf(stderr, "BENCH_KERNEL_S=%.9f\n", seconds);
}

static inline int bench_thread_count(void)
{
    const char *env = getenv("BENCH_THREADS");
    if (env != NULL && *env != '\0') {
        char *end = NULL;
        long v = strtol(env, &end, 10);
        if (end != env && *end == '\0' && v > 0 && v <= 4096)
            return (int)v;
        fprintf(stderr, "warning: ignoring invalid BENCH_THREADS='%s'\n", env);
    }
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    return n > 0 ? (int)n : 1;
}

#endif /* BENCH_COMMON_H */
