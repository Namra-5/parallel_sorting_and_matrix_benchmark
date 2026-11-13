#include <string.h>
#include "msort.h"

void msort_merge(int *a, int *tmp, int l, int m, int r)
{
    int n1 = m - l + 1;
    if (n1 <= 0 || m >= r)
        return;                       /* one side empty: already merged */

    memcpy(tmp + l, a + l, (size_t)n1 * sizeof(int));

    int i = l, j = m + 1, k = l;
    while (i <= m && j <= r)
        a[k++] = (tmp[i] <= a[j]) ? tmp[i++] : a[j++];
    while (i <= m)
        a[k++] = tmp[i++];
    /* leftover a[j..r] is already in place */
}

void msort_seq(int *a, int *tmp, int l, int r)
{
    if (l >= r)
        return;
    int m = l + (r - l) / 2;
    msort_seq(a, tmp, l, m);
    msort_seq(a, tmp, m + 1, r);
    msort_merge(a, tmp, l, m, r);
}

void msort_merge_runs(int *a, int *tmp, int *bounds, int nruns)
{
    while (nruns > 1) {
        int out = 0;
        for (int i = 0; i + 1 < nruns; i += 2) {
            msort_merge(a, tmp, bounds[i], bounds[i + 1] - 1, bounds[i + 2] - 1);
            bounds[out++] = bounds[i];
        }
        if (nruns % 2)
            bounds[out++] = bounds[nruns - 1];
        bounds[out] = bounds[nruns];
        nruns = out;
    }
}
