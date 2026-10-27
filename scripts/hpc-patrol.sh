#!/usr/bin/env bash
# Manage only this MVP's Nav2 process groups, leaving Isaac and its desktop intact.
set -euo pipefail
environment=$(realpath "${IC382_ENV_ROOT:-$HOME/Desktop/IC382}")
checkout=$(realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)")
relative=${checkout#"$environment/"}
[[ "$relative" != "$checkout" && "$relative" != ../* ]] || { echo 'Robot checkout must be inside the simulation project'; exit 1; }
container_checkout="/workspace/$relative"
if [[ -z "${SLURM_JOB_ID:-}" && "${1:-status}" != start ]]; then
  job=$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -n1)
  [[ -n "$job" ]] || { echo 'No running course GPU job'; exit 1; }
  exec srun --jobid="$job" --overlap -N1 -n1 "$0" "$@" </dev/null
fi
cd "$environment"
patrol_pids() {
  pgrep -u "$(id -u)" -f '^/usr/bin/python3 /opt/ros/humble/bin/ros2 launch ic382_navigation (patrol|desk_navigation).launch.py' || true
}
case "${1:-status}" in
  stop)
    for pid in $(patrol_pids); do
      group=$(ps -p "$pid" -o pgid= | tr -d ' ')
      [[ -n "$group" && "$group" != "$(ps -p $$ -o pgid= | tr -d ' ')" ]] || exit 1
      echo "Stopping verified MVP launch pid=$pid process_group=$group"
      kill -INT -- "-$group" 2>/dev/null || true
      sleep 3
      # The launch parent can exit before its component/container children.
      kill -TERM -- "-$group" 2>/dev/null || true
      sleep 2
      # A lifecycle component can hang during shutdown after its parent exits.
      kill -KILL -- "-$group" 2>/dev/null || true
    done
    ;;
  start)
    "$checkout/scripts/hpc-patrol.sh" check
    shift
    mkdir -p "$checkout/results"
    nohup setsid flock -n "$environment/cache/navigation-mvp.lock" \
      "$checkout/scripts/hpc-ros.sh" bash "$container_checkout/scripts/run-course-navigation.sh" \
      "$@" >"$checkout/results/patrol-launch.log" 2>&1 </dev/null &
    echo "Desk navigation started: $! (motion awaits /ic382/inspect_desk action)"
    ;;
  check)
    [[ -z "$(patrol_pids)" ]] || { echo 'MVP already running; use stop first'; exit 1; }
    if pgrep -u "$(id -u)" -f '^/usr/bin/python3 /opt/ros/humble/bin/ros2 launch (nav2_bringup|ic382_bringup)' >/dev/null; then
      echo 'Existing course navigation is running; stop its verified process group before starting MVP'
      exit 1
    fi
    if pgrep -u "$(id -u)" -f '^/opt/ros/humble/lib/rclcpp_components/component_container_isolated .*__node:=nav2_container' >/dev/null; then
      echo 'An existing Nav2 component container is still running; inspect and stop it first'
      exit 1
    fi
    ;;
  status)
    for pid in $(patrol_pids); do ps -p "$pid" -o pid,pgid,args | cut -c1-220; done
    ;;
  *) echo 'Usage: hpc-patrol.sh start [LAUNCH_ARGUMENT:=value ...] | stop | status';exit 1;;
esac
