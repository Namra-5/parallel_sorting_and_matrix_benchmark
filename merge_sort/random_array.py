#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print <size> random integers in [1, 10000], tab-separated, to stdout.

Usage: ./random_array.py <size> [seed]
With a seed the output is exactly reproducible (the benchmark harness always
passes one); without it the numbers differ on every call.
"""

import sys
import random

if len(sys.argv) not in (2, 3):
    sys.stderr.write("Usage: ./random_array.py <size> [seed]\n")
    sys.exit(1)

try:
    size = int(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) == 3 else None
except ValueError:
    sys.stderr.write("size and seed must be integers\n")
    sys.exit(1)

if size < 0:
    sys.stderr.write("size must not be negative\n")
    sys.exit(1)

if seed is not None:
    random.seed(seed)

arr = [str(random.randint(1, 10000)) for _ in range(size)]
print("\t".join(arr))
