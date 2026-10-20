#!/usr/bin/env bash
set -euo pipefail
project="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v ros2 >/dev/null 2>&1; then
  echo "Source ROS2 Humble inside the simulator's ROS2 runtime/namespace first." >&2
  exit 2
fi
if [[ "${ROS_DISTRO:-}" != humble ]]; then
  echo "ROS_DISTRO must be humble." >&2
  exit 2
fi
if [[ ! -f "$project/ros2_ws/install/setup.bash" ]]; then
  echo "Build ros2_ws first (colcon build), then retry." >&2
  exit 2
fi
set +u
source "$project/ros2_ws/install/setup.bash"
set -u
commit="$(git -C "$project" rev-parse HEAD)"
exec ros2 run ic382_bringup bridge_probe --commit "$commit" --output "$project/results/bridge.json" "$@"

