#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import random

if len(sys.argv) != 2:
    print("Usage: ./random_array.py <size>")
    sys.exit(1)

try:
    size = int(sys.argv[1])
except ValueError:
    print("Size must be an integer")
    sys.exit(1)

# generate random integers between 1 and 10000
arr = [str(random.randint(1, 10000)) for _ in range(size)]

# print to stdout separated by tabs
print("\t".join(arr))
