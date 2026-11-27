#!/usr/bin/env bash
# Read-only live display for the unattended benchmark. It never touches the benchmark. Press q to exit (Ctrl-C is ignored on purpose).
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2
LOGD=uni_logs; PROG=$LOGD/progress.txt; trap '' INT
G=$'\e[1;30;42m'; R=$'\e[1;37;41m'; N=$'\e[0m'; fr=('|' '/' '-' '\'); i=0
while true; do
  clear
  run=0; [ -f $LOGD/driver.pid ] && kill -0 "$(cat $LOGD/driver.pid 2>/dev/null)" 2>/dev/null && run=1
  fin=0; tail -n1 "$PROG" 2>/dev/null | grep -q 'driver finished' && fin=1
  if [ $run = 1 ]; then echo "${G} BENCHMARK RUNNING ${fr[i%4]}  Please do NOT close this window, shut down or restart this PC ${N}"
  elif [ $fin = 1 ]; then echo "${G} BENCHMARK FINISHED. Results are saved. ${N}"
  else echo "${R} BENCHMARK IS NOT RUNNING (stopped?) ${N}"; fi
  echo " Now: $(date '+%a %d %b %H:%M:%S')   (display refreshes every 15 s; it only reads files)"
  st=$(grep ' START ' "$PROG" 2>/dev/null | tail -1)
  if [ -n "$st" ]; then
    t0=$(date -d "${st%% *}" +%s 2>/dev/null) && echo " Current session: $(echo "$st" | sed 's/^[^ ]* START //') | running for $(( ($(date +%s)-t0)/60 )) min"
  fi
  act=$(ls -t $LOGD/uni_s*.log 2>/dev/null | head -1)
  if [ -n "$act" ]; then
    n=$(grep -c 'rep=' "$act"); bad=$(grep 'rep=' "$act" | grep -vc ' ok$')
    ago=$(( $(date +%s) - $(stat -c %Y "$act") ))
    echo " Runs finished so far in this session: $n | failed: $bad | last run finished $((ago/60)) min $((ago%60)) s ago"
    echo " (At large matrix sizes a single run can take several minutes, so a quiet log is normal.)"
    echo; echo " Latest runs:"; tail -n 5 "$act" | cut -c1-110 | sed 's/^/   /'
  fi
  echo; echo " Finished sessions:"; grep -E 'POSTPROCESS ok' "$PROG" 2>/dev/null | sed 's/^[^ ]* POSTPROCESS ok /   done: /'
  echo; echo " (press q to exit this display; the benchmark keeps running either way)"
  i=$((i+1)); key=""; read -r -t 15 -n 1 key 2>/dev/null; [ "$key" = q ] || [ "$key" = Q ] && break
done
clear; echo "display closed (the benchmark itself is not affected). Check with ./uni_status.sh"
