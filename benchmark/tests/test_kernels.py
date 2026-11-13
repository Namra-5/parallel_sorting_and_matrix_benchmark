"""Regression tests: build every C binary and check it against an independent Python oracle on the awkward inputs
that used to break (n not divisible by the rank count, fewer elements than threads, empty input, non-square matrices,
missing trailing newline, malformed files). Skipped automatically when gcc/make (or mpicc/mpirun) are missing."""
import importlib.util
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

B = Path(__file__).resolve().parents[1]
ROOT = B.parent
spec = importlib.util.spec_from_file_location("run_benchmark", B / "run_benchmark.py")
rb = importlib.util.module_from_spec(spec)
sys.modules["run_benchmark"] = rb
spec.loader.exec_module(rb)

HAVE_C = shutil.which("gcc") and shutil.which("make")
HAVE_MPI = shutil.which("mpicc") and shutil.which("mpirun")
pytestmark = pytest.mark.skipif(not HAVE_C, reason="gcc and make required")
# cores=1 makes the harness add --oversubscribe (OpenMPI) for every np > 1, whatever machine the tests run on
CTX = {"cores": 1, "flavor": rb.mpi_flavor() if shutil.which("mpirun") else "none"}


@pytest.fixture(scope="module")
def sort_models():
    return _build(ROOT / "merge_sort")


@pytest.fixture(scope="module")
def mat_models():
    return _build(ROOT / "matrix_multiplication")


def _build(wdir):
    models = rb.make_all(wdir, bool(HAVE_MPI))
    assert {"seq", "omp", "thread2"} <= set(models)
    return wdir, models


def run(wdir, model, inputs, workers):
    cmd, env, _ = rb.build_cmd(model, wdir, [str(i) for i in inputs], workers, CTX)
    p = subprocess.run(cmd, capture_output=True, env=env, timeout=120)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def plan(models):
    cases = [("seq", 1)] + [("omp", w) for w in (1, 3, 8)] + [("thread2", w) for w in (1, 3, 8, 16)]
    if "mpi" in models:
        cases += [("mpi", w) for w in (1, 2, 3, 7)]
    return cases


@pytest.mark.parametrize("n", [0, 1, 3, 7, 11, 1001])
def test_merge_sort_matches_python_sorted(sort_models, tmp_path, n):
    wdir, models = sort_models
    rnd = random.Random(n)
    vals = [rnd.randint(-50, 10000) for _ in range(n)]
    f = tmp_path / "a.txt"
    f.write_text("\t".join(map(str, vals)) + "\n")
    expected = "".join(f"{v}\t" for v in sorted(vals)) + "\n"
    for model, w in plan(models):
        rc, out, err = run(wdir, model, [f], w)
        assert rc == 0 and out == expected, f"{model} w={w} n={n}: rc={rc} {err[:200]}"


def matmul_text(a, b):
    lines = []
    for i in range(len(a)):
        row = ""
        for j in range(len(b[0])):
            acc = 0.0
            for k in range(len(b)):
                acc += a[i][k] * b[k][j]          # same summation order as the C code, IEEE double
            row += "%f\t" % acc
        lines.append(row)
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("shape", [(1, 1, 1), (5, 4, 5), (7, 3, 2), (13, 6, 9)])
def test_matrix_product_matches_python_bit_for_bit(mat_models, tmp_path, shape):
    wdir, models = mat_models
    r, k, c = shape
    rnd = random.Random(sum(shape))
    a = [[rnd.uniform(0, 9999) for _ in range(k)] for _ in range(r)]
    b = [[rnd.uniform(0, 9999) for _ in range(c)] for _ in range(k)]
    fa, fb = tmp_path / "a.txt", tmp_path / "b.txt"
    fa.write_text("".join("\t".join(map(repr, row)) + "\n" for row in a))
    fb.write_text("".join("\t".join(map(repr, row)) + "\n" for row in b))
    expected = matmul_text(a, b)
    for model, w in plan(models):
        rc, out, err = run(wdir, model, [fa, fb], w)
        assert rc == 0 and out == expected, f"{model} w={w} shape={shape}: rc={rc} {err[:200]}"


def test_matrix_without_trailing_newline_keeps_last_row(mat_models, tmp_path):
    wdir, _ = mat_models
    (tmp_path / "a.txt").write_text("1\t2\n3\t4")                 # no final newline
    (tmp_path / "i.txt").write_text("1\t0\n0\t1\n")
    rc, out, _ = run(wdir, "seq", [tmp_path / "a.txt", tmp_path / "i.txt"], 1)
    assert rc == 0 and out == "1.000000\t2.000000\t\n3.000000\t4.000000\t\n"


@pytest.mark.parametrize("content", ["", "1\t2\t3\n4\t5\t6\n7\t8\n"])
def test_malformed_matrix_fails_loudly(mat_models, tmp_path, content):
    wdir, _ = mat_models
    (tmp_path / "bad.txt").write_text(content)
    rc, out, err = run(wdir, "seq", [tmp_path / "bad.txt", tmp_path / "bad.txt"], 1)
    assert rc != 0 and out == "" and "Error" in err


def test_dimension_mismatch_and_missing_file_fail_loudly(mat_models, tmp_path):
    wdir, _ = mat_models
    (tmp_path / "a.txt").write_text("1\t2\n3\t4\n")
    (tmp_path / "b.txt").write_text("1\t2\t3\n")
    assert run(wdir, "seq", [tmp_path / "a.txt", tmp_path / "b.txt"], 1)[0] != 0
    assert run(wdir, "seq", [tmp_path / "nope.txt", tmp_path / "b.txt"], 1)[0] != 0


def test_sort_rejects_non_integer_token(sort_models, tmp_path):
    wdir, _ = sort_models
    (tmp_path / "a.txt").write_text("3\t1\tabc\t2\n")          # used to be silently truncated to [3, 1]
    rc, out, err = run(wdir, "seq", [tmp_path / "a.txt"], 1)
    assert rc != 0 and out == "" and "not an integer" in err


def test_timing_goes_to_stderr_only(sort_models, tmp_path):
    wdir, _ = sort_models
    (tmp_path / "a.txt").write_text("2\t1\n")
    rc, out, err = run(wdir, "seq", [tmp_path / "a.txt"], 1)       # build_cmd sets BENCH_TIMING=1
    assert rc == 0 and out == "1\t2\t\n" and "BENCH_KERNEL_S=" in err


def test_omp_merge_sort_really_uses_several_threads(sort_models, tmp_path):
    """Regression: nested `parallel sections` ran on a team of one (libgomp default max-active-levels = 1)."""
    wdir, _ = sort_models
    src = (ROOT / "merge_sort" / "src" / "omp.c").read_text()
    probe = src.replace("        msort_seq(a, tmp, l, r);\n        return;",
                        '        fprintf(stderr, "LEAF %d\\n", omp_get_thread_num());\n        msort_seq(a, tmp, l, r);\n        return;')
    assert probe != src
    (tmp_path / "probe.c").write_text(probe)
    exe = tmp_path / "probe"
    subprocess.run(["gcc", "-O2", "-std=gnu99", "-fopenmp", f"-I{ROOT / 'merge_sort/src'}", f"-I{ROOT / 'common'}",
                    "-o", str(exe), str(ROOT / "merge_sort/src/array.c"), str(ROOT / "merge_sort/src/msort.c"),
                    str(tmp_path / "probe.c")], check=True)
    rnd = random.Random(1)
    (tmp_path / "big.txt").write_text("\t".join(str(rnd.randint(1, 10**6)) for _ in range(100000)) + "\n")
    # The old nested-sections code had a team size of one, so thread 0 ran every leaf in EVERY attempt. With tasks,
    # more than one thread takes work in practice; allow a few attempts so a heavily loaded CI runner cannot flake.
    seen = set()
    for _ in range(5):
        p = subprocess.run([str(exe), str(tmp_path / "big.txt")], capture_output=True,
                           env={**os.environ, "OMP_NUM_THREADS": "4"})
        seen |= {ln for ln in p.stderr.decode().splitlines() if ln.startswith("LEAF")}
        if len(seen) >= 2:
            break
    assert len(seen) >= 2, "all leaf sorts ran on one thread in 5 attempts: the OpenMP sort is not parallel"
