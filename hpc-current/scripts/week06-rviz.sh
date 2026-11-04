#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "${DISPLAY:-}" ]]; then
  DISPLAY=$(ps -u "$(id -u)" -o args= | awk '$1 ~ /\/Xvnc$/ {print $2;exit}')
  export DISPLAY
fi
[[ -n "$DISPLAY" ]] || { echo "Open Connect-Gui.cmd first to start your HPC desktop."; exit 1; }
export XAUTHORITY=/home/student/.Xauthority
exec "$project/scripts/week06-ros.sh" rviz2 -d /workspace/dev/week06.rviz --ros-args -p use_sim_time:=true
