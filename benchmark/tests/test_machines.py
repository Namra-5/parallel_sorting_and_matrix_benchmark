"""Tests of the multi-machine README generator (no compiler or MPI needed)."""
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

B = Path(__file__).resolve().parents[1]
RAW_FIELDS = ["workload", "model", "size", "workers", "oversubscribed", "rep", "order", "start_utc", "load1", "wall_s",
              "kernel_s", "exit_code", "output_sha256_16", "status", "stderr_head"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, B / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mt = load("machines_table")
sd = load("standardize")


def _session(root, name, workload, size, workers, reps, cores, cpu="Test CPU", bad=False, drop=False):
    """One synthetic measurement session written the way the harness and standardize.py write it."""
    rows = []
    cfg = [("seq", 1)] + [(m, w) for m in ("omp", "thread2", "mpi") for w in workers]
    for model, w in cfg:
        for rep in range(1, reps + 1):
            t = 8.0 / (0.8 * w + 0.2) * (1 + 0.01 * rep)
            rows.append([workload, model, size, w, w > cores, rep, 1, "2026-01-01T00:00:00+00:00", 0.1, t + 1, t, 0, "a",
                         "mismatch" if (bad and model == "omp" and w == workers[-1] and rep == 1) else "ok", ""])
    raw = pd.DataFrame(rows, columns=RAW_FIELDS)
    d = Path(root) / name
    d.mkdir(parents=True)
    cfg_df = sd.standardize(raw[raw["status"] == "ok"] if not bad else raw)
    if drop:
        raw = raw.iloc[1:]
    raw.to_csv(d / "raw_runs.csv", index=False)
    cfg_df.to_csv(d / "benchmark_results.csv", index=False)
    (d / "hardware_environment.json").write_text(json.dumps(
        {"cpu_model": cpu, "effective_cores": cores, "protocol": {"reps": reps, "sort_reps": reps}}))
    return d


def _machines(tmp_path, **kw):
    lap = tmp_path / "lap"
    _session(lap, "s1", "matrix", 100, [1, 2, 3], 3, 2)
    lap_dir = lap / "s1"                                            # a single-session machine is the folder itself
    pc = tmp_path / "pc"
    _session(pc, "a", "matrix", 100, [1, 2, 4], 5, 2)
    _session(pc, "b", "mergesort", 1000, [1, 2, 4], 3, 2, **kw)
    return lap_dir, pc


def test_block_is_generated_from_the_data(tmp_path):
    lap, pc = _machines(tmp_path)
    block = mt.render_block(lap, pc)
    assert block.startswith(mt.START) and block.endswith(mt.END)
    assert "All 80 recorded runs" in block and "(20 configurations in 2 sessions" in block
    assert "| Workload | Size | Model | 2 workers | 4 workers* |" in block
    assert "| Matrix multiplication | 100×100 | OpenMP |" in block and "| Merge sort | 1,000 | MPI |" in block
    assert "| Matrix multiplication | 100×100 | " in block.split("Laptop and desktop")[1]       # the shared size is compared
    assert "Merge sort | 1,000 |" not in block.split("Laptop and desktop")[1].split("**Key numbers**")[0]  # not shared: not compared
    assert "merge sort 1,000 (3 repetitions)" in block                                               # fewer than 5 repetitions is reported
    readme = "intro\n" + mt.START + "\nold\n" + mt.END + "\noutro"
    new = mt.replace_block(readme, block)
    assert new.startswith("intro\n") and new.endswith("\noutro") and "old" not in new


def test_refuses_a_run_that_is_not_ok(tmp_path):
    lap, pc = _machines(tmp_path, bad=True)
    with pytest.raises(SystemExit):
        mt.render_block(lap, pc)


def test_refuses_a_missing_repetition(tmp_path):
    lap, pc = _machines(tmp_path, drop=True)
    with pytest.raises(SystemExit):
        mt.render_block(lap, pc)


def test_refuses_sessions_that_share_a_size(tmp_path):
    lap, _ = _machines(tmp_path / "x")
    pc = tmp_path / "y"
    _session(pc, "a", "matrix", 100, [1, 2, 4], 3, 2)
    _session(pc, "b", "matrix", 100, [1, 2, 4], 3, 2)
    with pytest.raises(SystemExit):
        mt.render_block(lap, pc)


def test_refuses_sessions_from_different_cpus(tmp_path):
    lap, _ = _machines(tmp_path / "x")
    pc = tmp_path / "y"
    _session(pc, "a", "matrix", 100, [1, 2, 4], 3, 2, cpu="CPU A")
    _session(pc, "b", "mergesort", 1000, [1, 2, 4], 3, 2, cpu="CPU B")
    with pytest.raises(SystemExit):
        mt.render_block(lap, pc)


@pytest.mark.skipif(not (B / "results_pc_i5-13500_wsl2").exists(), reason="no second-machine dataset in this checkout")
def test_readme_machines_block_matches_the_committed_datasets():
    """Every number in the README machines block is generated; this fails if README and datasets ever diverge."""
    assert mt.main(["--check"]) == 0
