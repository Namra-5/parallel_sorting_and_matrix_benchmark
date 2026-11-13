#ifndef MSORT_H
#define MSORT_H

/* Shared merge-sort kernel used by ALL four execution models, so that the
 * benchmark compares parallelisation strategies and not four slightly
 * different sorting routines.
 *
 * All ranges are inclusive: a[l..r]. `tmp` is a scratch buffer with at least as
 * many ints as the array being sorted; concurrent calls on disjoint ranges may
 * share one scratch buffer because each call only touches tmp[l..m]. */

/* Merge the sorted ranges a[l..m] and a[m+1..r]. Either range may be empty. */
void msort_merge(int *a, int *tmp, int l, int m, int r);

/* Top-down recursive merge sort of a[l..r]. A range with l >= r is a no-op. */
void msort_seq(int *a, int *tmp, int l, int r);

/* Bottom-up merge of `nruns` consecutive sorted runs. Run i is
 * a[bounds[i] .. bounds[i+1]-1]; `bounds` has nruns+1 entries and is
 * overwritten. Runs may be empty and need not have equal length. */
void msort_merge_runs(int *a, int *tmp, int *bounds, int nruns);

#endif
