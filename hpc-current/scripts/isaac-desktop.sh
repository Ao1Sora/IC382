#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "${DISPLAY:-}" ]]; then
  DISPLAY=$(ps -u "$(id -u)" -o args= | awk '$1 ~ /\/Xvnc$/ {print $2;exit}')
  export DISPLAY
fi
if [[ -z "${SLURM_JOB_ID:-}" || -z "${DISPLAY:-}" ]]; then
  echo 'Open this launcher inside the GPU job VNC desktop.' >&2
  exit 1
fi
mkdir -p "$project/cache" "$project/logs"
if [[ "${1:-}" != '--isolated' ]]; then
  exec 9>"$project/cache/isaac-desktop.lock"
  if ! flock -n 9; then
    echo 'An IC382 Isaac Sim desktop session is already running.'
    exit 1
  fi
  exec python3 "$project/scripts/loopback-namespace.py" bash "$0" --isolated
fi
if [[ "${IC382_LOOPBACK_ONLY:-}" != 1 || $(ip -o link | wc -l) -ne 2 ]] || ! ip link show ic382-local >/dev/null 2>&1; then
  echo 'Refusing to start streaming outside the private loopback network.' >&2
  exit 1
fi
threads=${SLURM_CPUS_PER_TASK:-6}
export OMP_NUM_THREADS="$threads" OPENBLAS_NUM_THREADS="$threads" MKL_NUM_THREADS="$threads"
export LD_LIBRARY_PATH="$project/tools/cpp-runtime/lib:${LD_LIBRARY_PATH:-}"
unset VK_ICD_FILENAMES __EGL_VENDOR_LIBRARY_FILENAMES __GLX_VENDOR_LIBRARY_NAME
server_log="$project/logs/desktop-server.log"
client_log="$project/logs/desktop-client.log"
cd "$project/tools/isaacsim-4.5.0"
(
  exec 9>&-
  unset DISPLAY XAUTHORITY
  exec ./isaac-sim.streaming.sh --/plugins/carb.tasking.plugin/threadCount="$threads" \
    --/plugins/omni.tbb.globalcontrol/maxThreadCount="$threads" \
    --/persistent/physics/numThreads="$threads" \
    --/app/window/width=1280 --/app/window/height=720
) >"$server_log" 2>&1 &
server=$!
client=''
cleanup() {
  [[ -z "$client" ]] || kill -TERM "$client" 2>/dev/null || true
  kill -TERM "$server" 2>/dev/null || true
  for _ in {1..10}; do kill -0 "$server" 2>/dev/null || break; sleep 1; done
  kill -KILL "$server" 2>/dev/null || true
  wait "$server" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
echo 'Starting Isaac Sim. The streaming client will open when ready.'
echo 'This session uses a private local network. Online assets are unavailable.'
ready=0
for i in {1..240}; do
  if ! kill -0 "$server" 2>/dev/null; then
    tail -25 "$server_log"
    exit 1
  fi
  if grep -q 'app ready\|Full Streaming App is loaded' "$server_log" && ss -H -lnt | grep -q ':49100 '; then ready=1; break; fi
  if (( i % 15 == 0 )); then echo "Still starting ($i seconds). Log: $server_log"; fi
  sleep 1
done
if (( ! ready )); then echo "Startup timed out. See $server_log"; exit 1; fi
cd "$project/tools/webrtc-client/squashfs-root"
export APPDIR="$PWD"
echo 'In the client, use 10.238.38.1 and click Connect.'
./AppRun --disable-setuid-sandbox --disable-gpu --disable-features=WebRtcHideLocalIpsWithMdns >"$client_log" 2>&1 9>&- &
client=$!
wait "$client" || { tail -25 "$client_log"; exit 1; }
