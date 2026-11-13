"""Unit tests for the harness, the standardiser and the legacy extractor (no compiler or MPI needed)."""
import csv
import importlib.util
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

B = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, B / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


rb = load("run_benchmark")
le = load("legacy_extract")
sd = load("standardize")


@pytest.mark.parametrize("rc,sha,ref,to,expected", [
    (0, "aa", "aa", False, "ok"), (0, "bb", "aa", False, "mismatch"), (1, "", "aa", False, "failed"),
    (0, "aa", None, False, "no_reference"), (0, "aa", "aa", True, "timeout"), (1, "", None, False, "failed")])
def test_classify(rc, sha, ref, to, expected):
    assert rb.classify(rc, sha, ref, to) == expected


def test_run_hashed_reports_exit_code_stderr_and_kernel_time():
    code = "import sys;print('x');sys.stderr.write('boom\\nBENCH_KERNEL_S=0.25\\n');sys.exit(3)"
    r = rb.run_hashed([sys.executable, "-c", code], {}, 30)
    assert r.exit_code == 3 and "boom" in r.stderr and "BENCH" not in r.stderr
    assert r.kernel_s == pytest.approx(0.25) and not r.timed_out and r.wall_s > 0 and len(r.sha16) == 16


def test_run_hashed_hash_is_deterministic():
    cmd = [sys.executable, "-c", "print('same output')"]
    assert rb.run_hashed(cmd, {}, 30).sha16 == rb.run_hashed(cmd, {}, 30).sha16


def test_timeout_fires_for_a_silent_hang():
    """Regression: the old driver blocked in read() and reported a 25 s silent hang as a success."""
    t = time.perf_counter()
    r = rb.run_hashed([sys.executable, "-c", "import time; time.sleep(25)"], {}, 1.5)
    assert r.timed_out and time.perf_counter() - t < 10


def test_timeout_fires_for_slowly_printing_process():
    code = "import time\nfor i in range(60):\n print('x', flush=True); time.sleep(1)"
    t = time.perf_counter()
    r = rb.run_hashed([sys.executable, "-c", code], {}, 1.5)
    assert r.timed_out and time.perf_counter() - t < 10


def test_large_output_does_not_deadlock():
    r = rb.run_hashed([sys.executable, "-c", "import sys; sys.stdout.write('a'*5_000_000); sys.stderr.write('b'*2_000_000)"],
                      {}, 60)
    assert r.exit_code == 0 and not r.timed_out


def test_default_workers():
    assert rb.default_workers(1) == [1]
    assert rb.default_workers(4) == [1, 2, 4]
    assert rb.default_workers(6) == [1, 2, 4, 6]
    assert rb.default_workers(8) == [1, 2, 4, 8]


def test_build_cmd_flags_per_mpi_flavour():
    wdir = Path("/x")
    ctx = {"cores": 2, "flavor": "openmpi"}
    cmd, env, over = rb.build_cmd("mpi", wdir, ["in"], 4, ctx)
    assert over and "--oversubscribe" in cmd and cmd[-2:] == ["/x/bin/mpi", "in"]
    assert cmd[cmd.index("-np") + 1] == "4"
    cmd, _, over = rb.build_cmd("mpi", wdir, ["in"], 2, ctx)
    assert not over and "--oversubscribe" not in cmd
    cmd, _, over = rb.build_cmd("mpi", wdir, ["in"], 4, {"cores": 2, "flavor": "mpich"})
    assert over and "--oversubscribe" not in cmd and "--allow-run-as-root" not in cmd
    _, env, over = rb.build_cmd("omp", wdir, ["in"], 8, ctx)
    assert env["OMP_NUM_THREADS"] == "8" and over
    _, env, over = rb.build_cmd("thread2", wdir, ["in"], 2, ctx)
    assert env["BENCH_THREADS"] == "2" and env["OMP_NUM_THREADS"] == "1" and not over
    _, env, over = rb.build_cmd("seq", wdir, ["in"], 1, ctx)
    assert not over and env["BENCH_TIMING"] == "1"


def test_parse_time_formats():
    assert le.parse_time("0.014s") == 0.014
    assert le.parse_time("1m 46.573s") == pytest.approx(106.573)
    assert le.parse_time("37m 52.786s") == pytest.approx(2272.786)
    assert le.parse_time("0.247s¹") == 0.247
    assert le.parse_time("0.247s†") == 0.247


def test_committed_legacy_csv_matches_readme_and_flags_all_mpi(tmp_path):
    """Drift guard: README tables and the committed CSV must be identical; every MPI row is flagged."""
    out = tmp_path / "legacy.csv"
    le.main(["--out", str(out)])
    fresh = out.read_bytes()
    assert fresh == (B / "legacy_single_run_results.csv").read_bytes(), "README tables and CSV disagree: rerun legacy_extract.py"
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 44
    assert all(r["flag"] for r in rows if r["model"] == "mpi") and len([r for r in rows if r["model"] == "mpi"]) == 11
    assert not any(r["flag"] for r in rows if r["model"] in ("omp", "thread2", "sequential"))
    sup = {(r["workload"], r["size"]) for r in rows if "implausible" in r["flag"]}
    assert ("matrix", "5000×5000") in sup and ("matrix", "2000×2000") in sup and ("mergesort", "500000") in sup
    s = next(r for r in rows if (r["workload"], r["size"], r["model"]) == ("matrix", "5000×5000", "thread2"))
    assert float(s["speedup_vs_seq"]) == pytest.approx(2272.786 / 1189.032, rel=1e-3)


HDR = ["workload", "model", "size", "workers", "oversubscribed", "rep", "wall_s", "kernel_s", "exit_code",
       "output_sha256_16", "status", "stderr_head"]


def frame(rows):
    return pd.DataFrame(rows, columns=HDR)


def test_standardize_math_and_exclusion_of_invalid_runs():
    df = frame([
        ["matrix", "seq", 100, 1, False, 1, 10.0, 8.0, 0, "a", "ok", ""], ["matrix", "seq", 100, 1, False, 2, 12.0, 8.0, 0, "a", "ok", ""],
        ["matrix", "seq", 100, 1, False, 3, 11.0, 8.0, 0, "a", "ok", ""],
        ["matrix", "omp", 100, 1, False, 1, 11.0, 8.0, 0, "a", "ok", ""],
        ["matrix", "omp", 100, 4, False, 1, 3.0, 2.0, 0, "a", "ok", ""], ["matrix", "omp", 100, 4, False, 2, 1.0, None, 1, "", "failed", "x"],
        ["matrix", "mpi", 100, 4, False, 1, 0.07, None, 1, "", "failed", "not enough slots"],
        ["matrix", "mpi", 100, 4, False, 2, 0.08, None, 1, "", "failed", "not enough slots"]])
    o = sd.standardize(df).set_index(["model", "workers"])
    assert o.loc[("omp", 4), "median_s"] == 3.0                       # the failed 1.0 s run is NOT used
    assert o.loc[("omp", 4), "speedup_vs_seq"] == pytest.approx(11.0 / 3.0)
    assert o.loc[("omp", 4), "efficiency"] == pytest.approx(11.0 / 3.0 / 4)
    assert o.loc[("omp", 4), "speedup_vs_1worker"] == pytest.approx(11.0 / 3.0)   # T_1 of the SAME model
    assert o.loc[("omp", 4), "kernel_speedup_vs_seq"] == pytest.approx(8.0 / 2.0)
    assert o.loc[("omp", 4), "status"] == "PARTIAL" and o.loc[("omp", 4), "n_failed"] == 1
    assert o.loc[("mpi", 4), "status"] == "INVALID" and pd.isna(o.loc[("mpi", 4), "speedup_vs_seq"])
    assert not o.loc[("mpi", 4), "scaling_valid"]


def test_baseline_is_matched_by_workload_and_size_only():
    df = frame([
        ["matrix", "seq", 100, 1, False, 1, 10.0, None, 0, "a", "ok", ""],
        ["matrix", "seq", 200, 1, False, 1, 80.0, None, 0, "b", "ok", ""],
        ["mergesort", "seq", 100, 1, False, 1, 1.0, None, 0, "c", "ok", ""],
        ["matrix", "omp", 200, 2, False, 1, 40.0, None, 0, "b", "ok", ""],
        ["mergesort", "omp", 100, 2, False, 1, 0.5, None, 0, "c", "ok", ""],
        ["matrix", "omp", 300, 2, False, 1, 5.0, None, 0, "z", "ok", ""]])      # size 300 has NO sequential baseline
    o = sd.standardize(df).set_index(["workload", "size", "model"])
    assert o.loc[("matrix", 200, "omp"), "speedup_vs_seq"] == pytest.approx(2.0)
    assert o.loc[("mergesort", 100, "omp"), "speedup_vs_seq"] == pytest.approx(2.0)
    assert pd.isna(o.loc[("matrix", 300, "omp"), "speedup_vs_seq"])           # never borrowed from another size


def test_oversubscribed_rows_are_never_scaling_valid():
    df = frame([
        ["matrix", "seq", 100, 1, False, 1, 10.0, None, 0, "a", "ok", ""],
        ["matrix", "omp", 8, 8, True, 1, 9.0, None, 0, "a", "ok", ""]])
    o = sd.standardize(df).set_index("workers")
    assert o.loc[8, "status"] == "ok" and not o.loc[8, "scaling_valid"]


def test_old_schema_without_kernel_column_still_works():
    df = frame([["matrix", "seq", 100, 1, False, 1, 10.0, None, 0, "a", "ok", ""]]).drop(columns=["kernel_s"])
    assert len(sd.standardize(df)) == 1


def test_missing_columns_fail_loudly():
    with pytest.raises(ValueError):
        sd.standardize(pd.DataFrame({"workload": ["x"]}))
