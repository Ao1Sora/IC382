#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project"
[[ -n "${SLURM_JOB_ID:-}" ]] || { echo 'Run this inside an allocated HPC GPU job.';exit 1; }
if [[ -z "${DISPLAY:-}" ]];then DISPLAY=$(ps -u "$(id -u)" -o args= | awk '$1 ~ /\/Xvnc$/ {print $2;exit}');export DISPLAY;fi
[[ -n "$DISPLAY" ]] || { echo 'Open Connect-Gui.cmd first.';exit 1; }
if [[ "${1:-}" != --isolated ]];then
 exec 9>cache/course601-stream.lock
 if ! flock -n 9; then
  if ./scripts/week06-ubuntu.sh -c 'wmctrl -xa isaacsim-webrtc-streaming-client' 2>/dev/null; then
    echo 'Existing course window shown.'
  else
    notify-send 'IC382 课程仿真' '正在加载场景，请稍候；无需重复双击。' 2>/dev/null || true
  fi
  exit 0
 fi
 notify-send 'IC382 课程仿真' '正在启动 Isaac Sim 6.0.1 和 ROS2 Humble，首次加载可能需要几分钟。' 2>/dev/null || true
 exec python3 scripts/loopback-namespace.py bash "$0" --isolated
fi
[[ "${IC382_LOOPBACK_ONLY:-}" == 1 ]] && ip link show ic382-local >/dev/null
pids=()
cleanup(){
 for p in "${pids[@]}";do kill -TERM -- "-$p" 2>/dev/null || kill -TERM "$p" 2>/dev/null || true;done
 sleep 2
 for p in "${pids[@]}";do kill -KILL -- "-$p" 2>/dev/null || true;done
}
trap cleanup EXIT
trap 'exit 130' INT TERM
launch(){ local name=$1;shift; setsid "$@" 9>&- >"logs/$name.log" 2>&1 & pids+=("$!");echo "Started $name ($!)"; }
launch course601-stream-simulation ./scripts/isaac601-python-rtx.sh /workspace/scripts/team-robot-simulation.py
server=${pids[0]}
launch course601-stream-scan-adapter ./scripts/week06-ros.sh python3 /workspace/scripts/week06-scan-adapter.py
launch course601-stream-loading bash -c 'while sleep 1; do echo "# 正在加载老师场景和 ROS2，请稍候……"; done | zenity --progress --pulsate --no-cancel --title="IC382 课程仿真启动中" --text="正在启动课程版本 Isaac Sim 6.0.1；首次编译可能较慢。" --width=420'
loading=${pids[-1]}
ready=0
for i in $(seq 1 1200);do
 kill -0 "$server" 2>/dev/null || { tail -c 5000 logs/course601-stream-simulation.log;exit 1; }
 if grep -q IC382_COURSE601_SIMULATION_RUNNING logs/course601-stream-simulation.log && ss -H -lnt | grep -q ':49100 ';then ready=1;break;fi
 if ((i%15==0));then echo "Starting course scene ($i seconds)";fi
 sleep 1
done
[[ "$ready" == 1 ]] || { echo 'Stream startup timed out';exit 1; }
kill -TERM -- "-$loading" 2>/dev/null || true
launch course601-stream-navigation ./scripts/week06-navigation.sh
sleep 10
./scripts/week06-ros.sh python3 /workspace/scripts/week06-initial-pose.py > logs/course601-stream-initial-pose.log 2>&1 9>&- || true
echo "IC382_COURSE601_STREAM_READY DISPLAY=$DISPLAY SERVER=10.238.38.1"
setsid ./scripts/isaac601-ubuntu.sh -c 'exec "/workspace/tools/webrtc-client-2.0.0/opt/Isaac Sim WebRTC Streaming Client/isaacsim-webrtc-streaming-client" --disable-setuid-sandbox --disable-gpu --disable-features=WebRtcHideLocalIpsWithMdns' > logs/course601-stream-client.log 2>&1 9>&- &
client=$!;pids+=("$client")
wait "$client"
