#!/usr/bin/env bash
# Unattended benchmark driver v2. Runs sessions s1a, s1b, s1c, s2, s3a, s3b in priority order and post-processes each.
#  * Never starts a session that is projected (estimate x1.4) to end after the deadline (default: today 17:00).
#  * Re-running is safe: finished sessions (.done) are skipped, an interrupted one is moved aside and redone.
#  * Stop before the next session:  touch uni_logs/STOP
#  * Preview the schedule only:     DRY=1 ./uni_run_all.sh          Other deadline:  DEADLINE="tomorrow 09:00" ./uni_run_all.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2
[ -f benchmark/run_benchmark.py ] || { echo "run this from the repository root"; exit 2; }
. "${VENV:-$HOME/venv}/bin/activate" || { echo "cannot activate venv"; exit 2; }
BENCH="${BENCH:-benchmark/run_benchmark.py}"; DRY="${DRY:-0}"
DL=$(date -d "${DEADLINE:-today 17:00}" +%s) || { echo "bad DEADLINE"; exit 2; }
LOGD="$PWD/uni_logs"; mkdir -p "$LOGD"; PROG="$LOGD/progress.txt"
say() { if [ "$DRY" = 1 ]; then echo "$*"; else echo "$(date -u +%FT%TZ) $*" | tee -a "$PROG"; fi; }
NOTES="Intel Core i5-13500 (6P+8E cores, 14 cores/20 threads, hybrid); Windows desktop running WSL2 Ubuntu 24.04; WSL reports 10 cores x 2 threads (not the real topology); 15 GiB visible to WSL; unattended run, plugged in, sleep disabled"
COMMON=(--workers 1 2 4 8 16 --cooldown 20 --warmup)
SCALE=1.0; VNOW=$(date +%s)
now_s() { if [ "$DRY" = 1 ]; then echo "$VNOW"; else date +%s; fi; }
WINCOPY="${WINCOPY:-/mnt/c/Users/Public}"
snapshot() {  # bundle EVERYTHING measured so far (finished, unfinished, logs) after every session; best-effort copy to the Windows side
  [ "$DRY" = 1 ] && return 0
  tar czf "$HOME/uni_results.tgz" benchmark/results/uni_s* "$LOGD" 2>/dev/null && sync \
    && say "SNAPSHOT saved ~/uni_results.tgz ($(du -h "$HOME/uni_results.tgz" | cut -f1))" || say "SNAPSHOT FAILED"
  [ -d "$WINCOPY" ] && cp "$HOME/uni_results.tgz" "$WINCOPY/uni_results.tgz" 2>/dev/null && say "SNAPSHOT also copied to $WINCOPY" || true
}

if [ "$DRY" != 1 ]; then
  if [ -f "$LOGD/driver.pid" ] && kill -0 "$(cat "$LOGD/driver.pid")" 2>/dev/null; then echo "a driver is already running (pid $(cat "$LOGD/driver.pid")); not starting a second one"; exit 3; fi
  echo $$ > "$LOGD/driver.pid"; trap 'rm -f "$LOGD/driver.pid"' EXIT
fi
[ "$DRY" = 1 ] || say "driver start | deadline $(date -d @"$DL" '+%a %H:%M') | load1=$(cut -d' ' -f1 /proc/loadavg) | $(free -g | awk '/Mem:/{print $7" GiB RAM available"}') | $(df -h . | awk 'NR==2{print $4" disk free"}')"
for t in gcc mpirun make; do command -v $t >/dev/null || { say "missing $t"; exit 2; }; done

session() {  # name expected_runs est_seconds timeout_per_run args...
  local name=$1 exp=$2 est=$3 to=$4; shift 4
  local out="benchmark/results/$name" log="$LOGD/$name.log"
  [ -e "$LOGD/STOP" ] && { say "STOP file found, not starting $name"; return 0; }
  [ -e "$out/.done" ] && { say "$name already done, skipping"; return 0; }
  local need; need=$(awk -v e="$est" -v s="$SCALE" 'BEGIN{printf "%d", e*s*1.4}')
  if [ $(( $(now_s) + need )) -gt "$DL" ]; then
    say "SKIP $name: needs about $((need/60)) min (estimate x1.4), would end after the deadline $(date -d @"$DL" +%H:%M)"; return 0; fi
  local cmd=(python3 "$BENCH" "$@" "${COMMON[@]}" --timeout "$to" --out-dir "$out" --notes "$NOTES | session $name")
  if [ "$DRY" = 1 ]; then
    echo "DRY: $name would start $(date -d @"$(now_s)" +%H:%M), expected end about $(date -d @$(( $(now_s) + ${est%.*} )) +%H:%M) (expect $exp runs)"
    VNOW=$(( VNOW + est )); return 0; fi
  [ -e "$out" ] && { mv "$out" "$out.incomplete_$(date +%s)"; say "moved unfinished $name aside"; }
  say "START $name (expect $exp runs, estimate $((est/60)) min)"
  local t0; t0=$(date +%s)
  "${cmd[@]}" > "$log" 2>&1; local rc=$?
  local dur=$(( $(date +%s) - t0 ))
  local last; last=$(grep -E '^[0-9]+ runs, [0-9]+ NOT ok' "$log" | tail -1)
  say "END $name rc=$rc after $((dur/60)) min | ${last:-no summary line}"
  if [ $rc -eq 0 ] && [[ "$last" == "$exp runs, 0 NOT ok"* ]]; then
    python3 benchmark/standardize.py --raw "$out/raw_runs.csv" --out "$out/benchmark_results.csv" >> "$log" 2>&1 \
      && python3 benchmark/plot_results.py --csv "$out/benchmark_results.csv" --out-dir "$out" >> "$log" 2>&1 \
      && lscpu > "$out/lscpu_full.txt" && grep -m1 'model name' /proc/cpuinfo > "$out/cpu_model.txt" \
      && cp "$log" "$out/run.log" && touch "$out/.done" && say "POSTPROCESS ok $name" || say "POSTPROCESS FAILED $name"
    if [ "$name" = uni_s1c ]; then   # matrix 2000 is the first big measurement: rescale later estimates to this machine's real speed
      SCALE=$(awk -v a="$dur" -v e="$est" 'BEGIN{r=a/e; if(r<0.8)r=0.8; if(r>3)r=3; printf "%.3f", r}')
      say "CALIBRATION: matrix-2000 session took $dur s vs estimate $est s -> later estimates x$SCALE"
    fi
  else
    say "SESSION NOT CLEAN: $name (rc=$rc, expected '$exp runs, 0 NOT ok')"
  fi
  snapshot
}

session uni_s1a  160  1330  900  --workload matrix    --matrix-sizes 1000 1500 --reps 5
session uni_s1b  720  1660  900  --workload mergesort --sort-sizes 50000 500000 5000000 --sort-reps 15
session uni_s1c   80  2050  900  --workload matrix    --matrix-sizes 2000 --reps 5
session uni_s2    80  7240  3600 --workload matrix    --matrix-sizes 3000 --reps 5
session uni_s3a   48  9970  7200 --workload matrix    --matrix-sizes 4000 --reps 3
session uni_s3b   48 18800  7200 --workload matrix    --matrix-sizes 5000 --reps 3
say "driver finished"
