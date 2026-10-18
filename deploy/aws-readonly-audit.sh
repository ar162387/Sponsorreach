#!/usr/bin/env bash
# Read-only resource check. Run through the existing SSM administration path.
set -eu
printf '\nMemory\n'
free -m
printf '\nCPU and load\n'
nproc
uptime
printf '\nDisk\n'
df -h /
printf '\nLargest processes (no command arguments or environment)\n'
ps -eo comm,rss,pcpu --sort=-rss | head -16
printf '\nService boundaries\n'
for unit in nimbess-hook nimbess-api vibecoderzz-voice postgresql caddy coturn; do
  systemctl show "$unit" --property=ActiveState,MemoryCurrent,MemoryPeak,MemoryHigh,MemoryMax,CPUUsageNSec --no-pager || true
done
printf '\nHistorical memory pressure counts\n'
journalctl -k --since '7 days ago' --no-pager 2>/dev/null | awk '/Out of memory|Killed process|oom-kill/ {n++} END {print "OOM log entries:", n+0}'
