#!/usr/bin/env bash
# Check-in script. Paste its whole output to Claude.      ./uni_status.sh          (status, takes < 1 s)
#                                                          ./uni_status.sh pack     (final visit only: bundle finished sessions)
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2
LOGD=uni_logs; PROG=$LOGD/progress.txt
[ -f "$PROG" ] || { echo "no $PROG yet: the driver has not been started from this folder"; exit 1; }
echo "=== NOW $(date '+%a %F %H:%M') local | WSL booted $(uptime -s) | $(uptime | sed 's/.*load/load/')"
echo "=== RAM $(free -g | awk '/Mem:/{print "available "$7" of "$2" GiB"}') | swap used $(free -g | awk '/Swap:/{print $3}') GiB | disk $(df -h . | awk 'NR==2{print $4" free"}')"
laststart=$(grep 'driver start' "$PROG" | tail -1 | cut -d' ' -f1)
boot=$(date -d "$(uptime -s)" +%s); ls=$(date -d "$laststart" +%s)
if [ "$boot" -gt "$ls" ]; then echo "!!! WSL RESTARTED after the driver started: the run was interrupted. Restart it (see below)."; fi
if tail -1 "$PROG" | grep -q 'driver finished'; then echo "=== DRIVER: FINISHED"
elif [ -f $LOGD/driver.pid ] && kill -0 "$(cat $LOGD/driver.pid)" 2>/dev/null; then echo "=== DRIVER: RUNNING (pid $(cat $LOGD/driver.pid))"
else echo "!!! DRIVER NOT RUNNING and did not finish. Restart:  nohup ./uni_run_all.sh > driver.out 2>&1 &"; fi
echo "=== progress.txt"; cat "$PROG"
active=$(ls -t $LOGD/uni_s*.log 2>/dev/null | head -1)
if [ -n "$active" ]; then
  n=$(grep -c 'rep=' "$active"); bad=$(grep 'rep=' "$active" | grep -vc ' ok$')
  echo "=== latest log $active: $n runs logged, $bad NOT ok"; tail -n 3 "$active" | cut -c1-140
  python3 - "$active" <<'E'
import re, sys, statistics as st
rx = re.compile(r'^(matrix|mergesort)\s+n=(\d+)\s+(\w+)\s+w=\s*(\d+)\s+rep=(\d+)/(\d+)\s+#\d+\s+wall=\s*([\d.]+)s kernel=\s*([\d.]+)s exit=(\d+)\s+(\S+)')
d = {}
for l in open(sys.argv[1]):
    m = rx.match(l)
    if m:
        w, n, mo, wk = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        d.setdefault((w, n, mo, wk), []).append((float(m.group(7)), float(m.group(8)), m.group(10)))
print("=== per configuration so far (kernel_s: median [min..max]; wall median; reps; statuses)")
for k in sorted(d):
    v = d[k]; ker = [x[1] for x in v]
    print(f"{k[0]} n={k[1]} {k[2]} w={k[3]}: kernel {st.median(ker):.4f} [{min(ker):.4f}..{max(ker):.4f}] wall {st.median([x[0] for x in v]):.3f} reps={len(v)} {','.join(sorted({x[2] for x in v}))}")
E
fi
if [ "${1:-}" = pack ]; then
  ls -d benchmark/results/uni_s* >/dev/null 2>&1 || { echo "nothing to pack"; exit 1; }
  tar czf "$HOME/uni_results.tgz" benchmark/results/uni_s* $LOGD && sync && echo "=== PACKED (finished=.done, others unfinished):" \
    && ls -d benchmark/results/uni_s* | while read d; do [ -e "$d/.done" ] && echo "  DONE       $d" || echo "  UNFINISHED $d"; done \
    && sha256sum "$HOME/uni_results.tgz"
fi
