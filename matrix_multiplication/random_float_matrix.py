#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# this small helper script generates test matrices of the given dimension and
# outputs them to stdout so that you can pipe it into files. The elements are
# separated by '\t'.
#
# Synopsis:
#   ./random_float_matrix.py 4 4 [seed]
#
# An optional third argument seeds the generator so the matrix is exactly
# reproducible (the benchmark harness always passes one).
#
# Author: Philipp Böhm

import sys
import random

try:
    dim_x, dim_y = int(sys.argv[1]), int(sys.argv[2])
    if len(sys.argv) > 3:
        random.seed(int(sys.argv[3]))
except Exception as e:
    sys.stderr.write("error parsing matrix dimensions (usage: rows cols [seed]) ...\n")
    raise

for row in range(0, dim_x):
    print("\t".join([str(random.uniform(0, 9999)) for x in range(0, dim_y)]))
