#!/usr/bin/env bash
# Foreground entry inside the existing simulation ROS container.
set -euo pipefail
checkout=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
environment=${IC382_CONTAINER_ENV_ROOT:-/workspace}
params="$environment/cache/team-nav2-params.yaml"
[[ -f "$checkout/ros2_ws/install/setup.bash" ]] || { echo 'Build robot-ros2/ros2_ws first'; exit 1; }
mkdir -p "$environment/cache" "$checkout/results/journal"
set +u
source "$checkout/ros2_ws/install/setup.bash"
set -u
python3 "$checkout/scripts/configure-course-navigation.py" --static --output "$params"
exec ros2 launch ic382_navigation desk_navigation.launch.py \
  params_file:="$params" log_directory:="$checkout/results/journal" "$@"
