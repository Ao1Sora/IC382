#!/usr/bin/env bash
# Run on Jetson: bash reset_robot.sh [--start|--dry-run]
set -eo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
restart=false
if [[ "${1:-}" == --start ]]; then restart=true; shift; fi
source /opt/ros/humble/setup.bash
if [[ -f "$HOME/wheeltec_ros2/install/setup.bash" ]]; then source "$HOME/wheeltec_ros2/install/setup.bash"; fi
if [[ -f "$root/ros2_ws/install/setup.bash" ]]; then source "$root/ros2_ws/install/setup.bash"; fi
python3 "$root/scripts/reset_robot.py" "$@"
if [[ "${1:-}" != --dry-run ]]; then
  stty sane 2>/dev/null || true
  printf '\033[?25h\033[0m'
fi
if "$restart"; then exec bash "$root/run.sh"; fi
