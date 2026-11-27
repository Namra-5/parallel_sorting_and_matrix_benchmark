#!/usr/bin/env bash
# Safe backup of everything measured so far. Run any time (about 1 s, harmless while the benchmark runs).
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2
ts=$(date +%Y%m%d_%H%M); B="$HOME/uni_backups"; W="${WINCOPY:-/mnt/c/Users/Public}/uni_backups"
mkdir -p "$B" || { echo "cannot create $B"; exit 1; }
f="$B/uni_backup_$ts.tgz"
tar czf "$f" benchmark/results/uni_s* uni_logs uni_run_all.sh uni_status.sh $( [ -f driver.out ] && echo driver.out ) 2>/dev/null
tar tzf "$f" >/dev/null || { echo "!!! ARCHIVE CORRUPT, run again"; exit 1; }
sync; sha256sum "$f" | tee "$f.sha256"
if mkdir -p "$W" 2>/dev/null && cp "$f" "$f.sha256" "$W/" && cmp "$f" "$W/$(basename "$f")"; then
  echo "OK copy verified in Windows: C:\\Users\\Public\\uni_backups\\$(basename "$f")"
else echo "!!! Windows copy FAILED (the WSL copy is still fine)"; fi
echo "contents:"; ls -d benchmark/results/uni_s* | while read d; do [ -e "$d/.done" ] && echo "  DONE       $d" || echo "  UNFINISHED $d"; done
for d in benchmark/results/uni_s*; do [ -e "$d/.done" ] && chmod -R a-w "$d"; done   # write-protect finished sessions against accidental deletion
echo "all backups:"; ls -1 "$B" | grep 'tgz$'
