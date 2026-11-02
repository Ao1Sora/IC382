#!/usr/bin/env bash
set -euo pipefail
checkout=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
environment=${IC382_ENV_ROOT:-"$HOME/Desktop/IC382"}
if [[ -z "${SLURM_JOB_ID:-}" && "${1:-status}" != start ]]; then
  job=$(squeue -h -u "$(id -un)" -t RUNNING -o '%i|%P' | awk -F'|' '$2=="h07gpuq1" {print $1;exit}')
  [[ -n "$job" ]] || { echo 'No running GPU job'; exit 1; }
  exec srun --jobid="$job" --overlap -N1 -n1 "$0" "$@" </dev/null
fi
pids(){ pgrep -u "$(id -u)" -f '^/usr/bin/python3 /opt/ros/humble/bin/ros2 launch ic382_navigation simulation.launch.py' || true; }
case "${1:-status}" in
  status) for pid in $(pids); do ps -p "$pid" -o pid,pgid,args; done ;;
  check) [[ -z "$(pids)" ]] || { echo 'Navigation already running'; exit 1; } ;;
  stop)
    for pid in $(pids); do
      group=$(ps -p "$pid" -o pgid= | tr -d ' ')
      [[ -n "$group" && "$group" != "$(ps -p $$ -o pgid= | tr -d ' ')" ]] || exit 1
      kill -INT -- "-$group"
    done ;;
  start)
    "$0" check
    mkdir -p "$checkout/results"
    nohup setsid flock -n "$environment/cache/navigation-mvp.lock" \
      "$checkout/scripts/hpc-ros.sh" bash /workspace/robot-ros2/scripts/run-course-navigation.sh \
      >"$checkout/results/patrol-launch.log" 2>&1 </dev/null &
    echo "NAVIGATION_START_PID=$!" ;;
  *) echo 'Usage: hpc-patrol.sh start|stop|status'; exit 1 ;;
esac
