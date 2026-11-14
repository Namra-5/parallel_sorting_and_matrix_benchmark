#!/usr/bin/env python3
"""Reproducible, self-validating benchmark driver for this repository's binaries.

It drives the repository's own Makefile targets (bin/seq, bin/omp, bin/thread2, bin/mpi) and fixes the weaknesses of the
old Test-Script.sh: every run's exit status is checked, every run's printed output is hashed and compared with the
sequential output for the same input, and every run has a working timeout. A crashed, hung or wrong run can therefore
never be reported as a fast one.

    python benchmark/run_benchmark.py --smoke                      # tiny sanity run (seconds); also what CI runs
    python benchmark/run_benchmark.py --workload matrix --matrix-sizes 500 1000 2000 --workers 1 2 4 --reps 3
    python benchmark/run_benchmark.py --workload mergesort --sort-sizes 5000 500000 --workers 1 2 4

What "workers" means for each model:
  seq      baseline, workers = 1
  omp      OMP_NUM_THREADS = workers
  thread2  BENCH_THREADS   = workers (read by the C code; default there = online CPUs)
  mpi      mpirun -np workers

Two times are recorded per run:
  wall_s    whole process, measured here: includes mpirun start-up, reading the text input and printing the result
  kernel_s  measured inside the program (BENCH_TIMING=1): the computation only (for MPI: scatter/compute/gather/merge)
Both are kept; wall_s is what `time` measured before, kernel_s is the clean scaling signal.

Oversubscription: a configuration with more workers than usable *physical* cores is flagged `oversubscribed=True`. It is
still run (and mpirun is given whichever oversubscribe flag it was found to accept, so the launch does not fail) but standardize.py never treats it as a
valid scaling data point.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
SEED = 20260101
SCHEMA_VERSION = 2
RAW_FIELDS = ["workload", "model", "size", "workers", "oversubscribed", "rep", "wall_s", "kernel_s", "exit_code",
              "output_sha256_16", "status", "stderr_head"]
KERNEL_RE = re.compile(r"^BENCH_KERNEL_S=([0-9.eE+-]+)\s*$", re.MULTILINE)
STDERR_KEEP = 64 * 1024  # bytes of stderr kept per run (the rest is drained and dropped)


# --------------------------------------------------------------------------------------------------------------------
# classification and process execution
# --------------------------------------------------------------------------------------------------------------------
def classify(exit_code: int, sha: Optional[str], ref_sha: Optional[str], timed_out: bool = False) -> str:
    """ok | failed | mismatch | timeout | no_reference. Only 'ok' rows may enter speedup statistics."""
    if timed_out:
        return "timeout"
    if exit_code != 0:
        return "failed"
    if ref_sha is None:
        return "no_reference"  # the sequential run for this input did not succeed, so nothing can be verified
    if sha != ref_sha:
        return "mismatch"
    return "ok"


class RunResult(NamedTuple):
    wall_s: float
    exit_code: int
    sha16: str
    stderr: str
    kernel_s: Optional[float]
    timed_out: bool


def _kill_tree(p: subprocess.Popen) -> None:
    """Kill the process and everything it spawned (mpirun starts the ranks as children)."""
    try:
        if os.name == "posix":
            os.killpg(p.pid, signal.SIGKILL)
        else:  # pragma: no cover - Windows is not a supported platform for the C code anyway
            p.kill()
    except (ProcessLookupError, PermissionError):
        pass


def run_hashed(cmd: list[str], env: dict, timeout: float) -> RunResult:
    """Run cmd, hash its stdout incrementally (matrix output can be hundreds of MB) and enforce `timeout` seconds.

    stdout and stderr are drained by helper threads, so the timeout is honoured even if the program hangs without
    printing anything (e.g. an MPI deadlock).
    """
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         start_new_session=(os.name == "posix"))
    digest = hashlib.sha256()
    err = bytearray()

    def pump_out() -> None:
        for chunk in iter(lambda: p.stdout.read1(1 << 16), b""):
            digest.update(chunk)

    def pump_err() -> None:
        for chunk in iter(lambda: p.stderr.read1(1 << 16), b""):
            if len(err) < STDERR_KEEP:
                err.extend(chunk[: STDERR_KEEP - len(err)])

    done = threading.Event()
    finished: list[float] = []

    def waiter() -> None:
        # A blocking wait returns the instant the child exits. Popen.wait(timeout=...) instead polls with sleeps of up
        # to 50 ms, which inflated and quantised every measured wall time.
        p.wait()
        finished.append(time.perf_counter())
        done.set()

    threads = [threading.Thread(target=f, daemon=True) for f in (pump_out, pump_err, waiter)]
    for t in threads:
        t.start()
    timed_out = False
    if not done.wait(timeout):
        timed_out = True
        _kill_tree(p)
        done.wait()
    wall = (finished[0] if finished else time.perf_counter()) - t0
    for t in threads:
        t.join(timeout=10)
    text = bytes(err).decode("utf-8", "replace")
    m = KERNEL_RE.search(text)
    kernel = float(m.group(1)) if m else None
    text = KERNEL_RE.sub("", text)
    rc = p.returncode if p.returncode is not None else -9
    return RunResult(wall, rc, digest.hexdigest()[:16], " ".join(text.split())[:160], kernel, timed_out)


# --------------------------------------------------------------------------------------------------------------------
# hardware / environment detection (every probe is best-effort: a missing tool must never crash the run)
# --------------------------------------------------------------------------------------------------------------------
def _out(cmd: list[str], timeout: float = 20) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def usable_logical_cores() -> int:
    """CPUs this process may actually use (honours taskset/cgroup cpusets, unlike os.cpu_count())."""
    try:
        return max(1, len(os.sched_getaffinity(0)))  # type: ignore[attr-defined]
    except AttributeError:
        return os.cpu_count() or 1


def cgroup_cpu_limit() -> Optional[float]:
    """CPU quota of a container (cgroup v2 then v1) in cores, or None if unlimited / unknown."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            return int(quota) / int(period)
        return None
    except Exception:
        pass
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        return quota / period if quota > 0 else None
    except Exception:
        return None


def physical_cores(logical: int) -> int:
    """Physical cores (SMT siblings counted once), capped by the usable logical CPUs. Falls back to `logical`."""
    n = 0
    if sys.platform.startswith("linux"):
        pairs = {ln for ln in _out(["lscpu", "-p=CORE,SOCKET"]).splitlines() if ln and not ln.startswith("#")}
        n = len(pairs)
    elif sys.platform == "darwin":
        txt = _out(["sysctl", "-n", "hw.physicalcpu"]).strip()
        n = int(txt) if txt.isdigit() else 0
    return max(1, min(n, logical)) if n else logical


def effective_cores() -> int:
    """The number of cores a scaling experiment may use before it counts as oversubscribed."""
    logical = usable_logical_cores()
    cores = physical_cores(logical)
    quota = cgroup_cpu_limit()
    if quota is not None:
        cores = min(cores, max(1, math.floor(quota + 1e-9)))
    return cores


def mpi_flavor() -> str:
    """openmpi | mpich | unknown. Informational only: launch flags are chosen by probing (mpi_launch_options)."""
    text = (_out(["mpirun", "--version"]) + _out(["mpiexec", "--version"])).lower()
    if "open mpi" in text or "open-mpi" in text or "prrte" in text or "prterun" in text:
        return "openmpi"  # PRRTE is the launcher of Open MPI 5; Debian/Ubuntu ship it as a separate package
    if "hydra" in text or "mpich" in text:
        return "mpich"
    return "unknown"


def mpi_launch_options(cores: int) -> dict:
    """Find, by actually launching a trivial program, which flags this mpirun needs and understands.

    Version strings are unreliable (Ubuntu 26's `mpirun` is PRRTE's `prterun` and never says "Open MPI"), and the flag
    spelling differs between releases, so each candidate is tested: an oversubscribed launch (cores + 2 ranks of
    `true`) must exit 0. A candidate that also prints a warning (deprecated spelling) is used only if no clean one works.
    Returns {"mpi_root": [...], "mpi_oversub": [...] or None}.
    """
    true_bin = shutil.which("true") or "/bin/true"

    def launch(args: list[str], np: int):
        try:
            return subprocess.run(["mpirun", *args, "-np", str(np), true_bin], capture_output=True, text=True,
                                  timeout=120, stdin=subprocess.DEVNULL)
        except Exception:
            return None

    root: list[str] = []
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        p = launch(["--allow-run-as-root"], 1)
        if p is not None and p.returncode == 0:
            root = ["--allow-run-as-root"]
    clean = noisy = None
    for cand in (["--oversubscribe"], ["--map-by", ":oversubscribe"]):
        p = launch(root + cand, cores + 2)
        if p is not None and p.returncode == 0:
            if not p.stderr.strip():
                clean = cand
                break
            noisy = noisy or cand
    return {"mpi_root": root, "mpi_oversub": clean or noisy}


def makefile_flags(wdir: Path) -> str:
    """Compiler flags exactly as the Makefile defines them (so the recorded value cannot drift from the build)."""
    vals = {}
    try:
        for line in (wdir / "Makefile").read_text().splitlines():
            m = re.match(r"^(TUNE|CFLAGS)\s*[:?]?=\s*(.*)$", line)
            if m:
                vals[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    flags = f"{vals.get('TUNE', '')} {vals.get('CFLAGS', '')}"
    return " ".join(re.sub(r"\$\([^)]*\)", "", flags).split())  # drop unexpanded $(EXTRA_CFLAGS)-style variables


def git_state() -> dict:
    head = _out(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    if not head:
        return {"commit": None, "dirty": None}
    dirty = bool(_out(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"]).strip())
    return {"commit": head, "dirty": dirty}


def hardware(ctx: dict, notes: str) -> dict:
    lscpu = {}
    for line in _out(["lscpu"]).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            lscpu[k.strip()] = v.strip()
    first = lambda cmd: (_out(cmd).splitlines() or [""])[0]
    mem = None
    try:
        mem = round(int(next(ln for ln in open("/proc/meminfo") if ln.startswith("MemTotal")).split()[1]) / 1048576, 2)
    except Exception:
        txt = _out(["sysctl", "-n", "hw.memsize"]).strip() if sys.platform == "darwin" else ""
        if txt.isdigit():
            mem = round(int(txt) / 2 ** 30, 2)
    governor = None
    try:
        governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text().strip()
    except Exception:
        pass
    return {
        "schema_version": SCHEMA_VERSION,
        "collected_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "os": platform.platform(), "python": platform.python_version(),
        "cpu_model": lscpu.get("Model name") or platform.processor() or None,
        "logical_cpus_usable": ctx["logical"], "physical_cores": ctx["physical"],
        "cgroup_cpu_limit": ctx["cgroup_limit"], "effective_cores": ctx["cores"],
        "cores_per_socket": lscpu.get("Core(s) per socket"), "threads_per_core": lscpu.get("Thread(s) per core"),
        "cpu_governor": governor, "memory_total_gib": mem,
        "gcc": first(["gcc", "--version"]), "mpirun": first(["mpirun", "--version"]), "mpi_flavor": ctx["flavor"],
        "mpi_launch_flags": {"root": ctx.get("mpi_root"), "oversubscribe": ctx.get("mpi_oversub")},
        "cflags_matrix": makefile_flags(ROOT / "matrix_multiplication"),
        "cflags_mergesort": makefile_flags(ROOT / "merge_sort"),
        "data_seed": SEED, "git": git_state(), "notes": notes,
    }


# --------------------------------------------------------------------------------------------------------------------
# build, data generation, command construction
# --------------------------------------------------------------------------------------------------------------------
def make_all(workload_dir: Path, want_mpi: bool) -> list[str]:
    """Build with the repo's own Makefile. Returns the models that are available (MPI is skipped if it cannot build)."""
    targets = [("sequential", "seq"), ("omp", "omp"), ("thread2", "thread2")] + ([("mpi", "mpi")] if want_mpi else [])
    models = []
    for target, binary in targets:
        r = subprocess.run(["make", target], cwd=workload_dir, capture_output=True, text=True)
        if r.returncode != 0 or not (workload_dir / "bin" / binary).exists():
            if target == "mpi":
                print(f"WARNING: building MPI in {workload_dir.name} failed - MPI skipped:\n{r.stderr[-600:]}",
                      file=sys.stderr)
                continue
            sys.exit(f"ERROR: `make {target}` failed in {workload_dir}:\n{r.stdout[-600:]}\n{r.stderr[-1200:]}")
        models.append(binary)
    return models


def _generate(argv: list[str], cwd: Path, path: Path) -> None:
    """Run a generator into a temp file and rename it, so an interrupted run can never leave a truncated input behind."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w") as fh:
        subprocess.run([sys.executable, *argv], cwd=cwd, stdout=fh, check=True)
    os.replace(tmp, path)


def gen_matrix(path: Path, n: int, salt: int) -> None:
    if not path.exists():
        _generate(["random_float_matrix.py", str(n), str(n), str(SEED + salt)], ROOT / "matrix_multiplication", path)


def gen_array(path: Path, n: int) -> None:
    if not path.exists():
        _generate(["random_array.py", str(n), str(SEED)], ROOT / "merge_sort", path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_cmd(model: str, wdir: Path, inputs: list[str], workers: int, ctx: dict):
    """Returns (command, environment, oversubscribed)."""
    binary = str(wdir / "bin" / model)
    env = os.environ.copy()
    env["BENCH_TIMING"] = "1"
    env["OMP_NUM_THREADS"] = "1"        # only the omp model may use more than one OpenMP thread
    env.pop("BENCH_THREADS", None)
    env["OMP_DYNAMIC"] = "false"
    over = workers > ctx["cores"] and model != "seq"
    if model == "omp":
        env["OMP_NUM_THREADS"] = str(workers)
        return [binary, *inputs], env, over
    if model == "thread2":
        env["BENCH_THREADS"] = str(workers)
        return [binary, *inputs], env, over
    if model == "mpi":
        cmd = ["mpirun", *ctx.get("mpi_root", [])]
        if over:
            cmd += ctx.get("mpi_oversub") or []  # without it the launcher refuses np > slots in ~0.06 s
        return cmd + ["-np", str(workers), binary, *inputs], env, over
    return [binary, *inputs], env, False


def default_workers(cores: int) -> list[int]:
    w = [1]
    while w[-1] * 2 <= cores:
        w.append(w[-1] * 2)
    if w[-1] != cores:
        w.append(cores)
    return w


# --------------------------------------------------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workload", choices=["matrix", "mergesort", "both"], default="both")
    ap.add_argument("--matrix-sizes", type=int, nargs="+", default=[500, 1000, 2000])
    ap.add_argument("--sort-sizes", type=int, nargs="+", default=[5000, 50000, 500000])
    ap.add_argument("--workers", type=int, nargs="+", default=None,
                    help="worker counts (default: 1, 2, 4, ... up to the physical cores, plus the core count)")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=3600.0, help="seconds per run")
    ap.add_argument("--cooldown", type=float, default=0.0,
                    help="seconds to sleep between repetitions (laptops throttle thermally during long runs)")
    ap.add_argument("--out-dir", default=None, help="default: benchmark/results (benchmark/results_smoke with --smoke)")
    ap.add_argument("--notes", default="EDIT: bare metal / WSL / VM, power plan or governor, background load.",
                    help="free text stored in hardware_environment.json")
    ap.add_argument("--smoke", action="store_true", help="tiny sizes, 1 rep (sanity check / CI)")
    ap.add_argument("--allow-failures", action="store_true", help="exit 0 even if some runs are not 'ok'")
    a = ap.parse_args(argv)
    if a.smoke:
        # 62 and 2001 are deliberately NOT divisible by 2 or 4 (the regression that used to corrupt MPI output),
        # and 3 workers exercises uneven decomposition and, on small machines, oversubscription.
        a.matrix_sizes, a.sort_sizes, a.reps = [62], [2001], 1
        if a.workers is None:
            a.workers = [1, 2, 3]
    if a.out_dir is None:
        a.out_dir = str(HERE / ('results_smoke' if a.smoke else 'results'))
    if min(a.matrix_sizes + a.sort_sizes) < 1 or a.reps < 1 or (a.workers and min(a.workers) < 1):
        ap.error("sizes, --reps and --workers must be positive")
    if a.cooldown < 0:
        ap.error("--cooldown must not be negative")
    return a


def main(argv=None) -> int:
    a = parse_args(argv)
    if os.name == "nt":
        sys.exit("The C benchmarks need a POSIX environment: run this inside WSL (or Linux/macOS).")
    if shutil.which("make") is None or shutil.which("gcc") is None:
        sys.exit("ERROR: `make` and `gcc` are required (see README prerequisites).")
    logical = usable_logical_cores()
    ctx = {"logical": logical, "physical": physical_cores(logical), "cgroup_limit": cgroup_cpu_limit(),
           "cores": effective_cores(), "flavor": mpi_flavor() if shutil.which("mpirun") else "none",
           "mpi_root": [], "mpi_oversub": None}
    workers = a.workers or default_workers(ctx["cores"])
    want_mpi = shutil.which("mpicc") is not None and shutil.which("mpirun") is not None
    if not want_mpi:
        print("WARNING: mpicc/mpirun not found - MPI is skipped", file=sys.stderr)
    if want_mpi:
        ctx.update(mpi_launch_options(ctx["cores"]))
        if ctx["mpi_oversub"] is None:
            print("WARNING: no working oversubscribe flag found for this mpirun: MPI runs with more ranks than slots "
                  "will fail and be recorded as 'failed'", file=sys.stderr)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = HERE / "data"
    data.mkdir(exist_ok=True)
    (out / "hardware_environment.json").write_text(json.dumps(hardware(ctx, a.notes), indent=2))
    print(f"effective cores: {ctx['cores']} (physical {ctx['physical']}, usable logical {ctx['logical']}); "
          f"workers: {workers}; MPI: {ctx['flavor']} (oversubscribe flag: {ctx.get('mpi_oversub')})", flush=True)

    jobs = []
    if a.workload in ("matrix", "both"):
        jobs.append(("matrix", ROOT / "matrix_multiplication", a.matrix_sizes))
    if a.workload in ("mergesort", "both"):
        jobs.append(("mergesort", ROOT / "merge_sort", a.sort_sizes))

    manifest, n_rows, bad = {}, 0, []
    with (out / "raw_runs.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RAW_FIELDS)
        for workload, wdir, sizes in jobs:
            models = make_all(wdir, want_mpi)
            for n in sizes:
                if workload == "matrix":
                    fa, fb = data / f"mat_{n}_a.txt", data / f"mat_{n}_b.txt"
                    gen_matrix(fa, n, 1)
                    gen_matrix(fb, n, 2)
                    paths = [fa, fb]
                else:
                    fa = data / f"array_{n}.txt"
                    gen_array(fa, n)
                    paths = [fa]
                for pth in paths:
                    manifest[pth.name] = {"bytes": pth.stat().st_size, "sha256": sha256_file(pth)}
                inputs = [str(pth) for pth in paths]
                plan = [("seq", 1)] + [(m, w) for m in ("omp", "thread2", "mpi") if m in models for w in workers]
                ref_sha = None
                # repetitions are the OUTER loop so slow drift (thermal, background load) hits all models alike
                for rep in range(1, a.reps + 1):
                    if rep > 1 and a.cooldown > 0:
                        time.sleep(a.cooldown)
                    for model, w in plan:
                        cmd, env, over = build_cmd(model, wdir, inputs, w, ctx)
                        r = run_hashed(cmd, env, a.timeout)
                        if model == "seq" and r.exit_code == 0 and not r.timed_out and ref_sha is None:
                            ref_sha = r.sha16
                        status = classify(r.exit_code, r.sha16, ref_sha, r.timed_out)
                        row = [workload, model, n, w, over, rep, f"{r.wall_s:.6f}",
                               "" if r.kernel_s is None else f"{r.kernel_s:.9f}", r.exit_code, r.sha16, status,
                               r.stderr]
                        writer.writerow(row)
                        fh.flush()  # a crash or Ctrl-C in a multi-hour run keeps everything measured so far
                        n_rows += 1
                        if status != "ok":
                            bad.append(row)
                        ktxt = "-" if r.kernel_s is None else f"{r.kernel_s:.4f}s"
                        print(f"{workload:9s} n={n:<7d} {model:8s} w={w:<3d}{'*' if over else ' '} rep={rep} "
                              f"wall={r.wall_s:9.3f}s kernel={ktxt:>10s} exit={r.exit_code} {status}", flush=True)
    (out / "inputs_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\n{n_rows} runs, {len(bad)} NOT ok -> {out / 'raw_runs.csv'}   (* = oversubscribed: more workers than cores)")
    if bad:
        print("Non-ok runs are excluded from speedup statistics; status and stderr are in raw_runs.csv.")
        for r in bad[:10]:
            print(f"  {r[0]} {r[1]} n={r[2]} w={r[3]} -> {r[10]} (exit {r[8]}): {r[11][:100]}")
    return 1 if (bad and not a.allow_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
