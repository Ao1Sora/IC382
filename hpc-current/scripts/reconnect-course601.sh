#!/usr/bin/env bash
# Reopen only the viewer in the existing simulation's isolated network.
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
 job=$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -n1)
 [[ -n "$job" ]] || { echo 'No running course GPU job'; exit 1; }
 exec srun --jobid="$job" --overlap -N1 -n1 "$0" </dev/null
fi
export DISPLAY=${DISPLAY:-$(ps -u "$(id -u)" -o args= | awk '$1 ~ /\/Xvnc$/ {print $2;exit}')}
if "$project/scripts/week06-ubuntu.sh" -c 'wmctrl -xa isaacsim-webrtc-streaming-client' 2>/dev/null; then
 echo 'Existing viewer shown.'
 exit 0
fi
server=$(cat "$project/cache/course601-server.pid" 2>/dev/null || true)
[[ "$server" =~ ^[0-9]+$ ]] && kill -0 "$server" 2>/dev/null && ps -p "$server" -o args= | grep -q isaacsim-6.0.1 || { echo 'Simulation is not running; use the course desktop launcher'; exit 1; }
group=$(ps -p "$server" -o pgid= | tr -d ' ')
nohup setsid nsenter -t "$group" -U --preserve-credentials -n \
 "$project/scripts/isaac601-ubuntu.sh" -c 'exec "/workspace/tools/webrtc-client-2.0.0/opt/Isaac Sim WebRTC Streaming Client/isaacsim-webrtc-streaming-client" --disable-setuid-sandbox --disable-gpu --disable-features=WebRtcHideLocalIpsWithMdns' \
 >"$project/logs/course601-reconnected-client.log" 2>&1 </dev/null &
viewer=$!
# A viewer reopened outside the original supervisor must close if its server exits.
nohup bash -c 'while kill -0 "$1" 2>/dev/null && kill -0 "$2" 2>/dev/null; do sleep 2; done; if ! kill -0 "$1" 2>/dev/null; then kill -TERM -- "-$2" 2>/dev/null || true; fi' -- "$server" "$viewer" >/dev/null 2>&1 </dev/null &
echo "Viewer reopened: $viewer; simulation retained."
