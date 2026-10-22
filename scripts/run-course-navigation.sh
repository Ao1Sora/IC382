#!/usr/bin/env bash
# Foreground entry inside the existing simulation ROS container.
set -euo pipefail
checkout=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
environment=${IC382_CONTAINER_ENV_ROOT:-/workspace}
route=${1:-"$checkout/ros2_ws/src/ic382_navigation/config/course_demo_route.yaml"}
params="$environment/cache/team-nav2-params.yaml"
[[ -f "$checkout/ros2_ws/install/setup.bash" ]] || { echo 'Build robot-ros2/ros2_ws first'; exit 1; }
mkdir -p "$environment/cache" "$checkout/results/journal"
set +u
source "$checkout/ros2_ws/install/setup.bash"
set -u
python3 "$checkout/scripts/configure-course-navigation.py" --environment "$environment" --output "$params"
exec ros2 launch ic382_navigation patrol.launch.py \
  map:="$environment/output/maps/teacher-scene-20261021/scene_map.yaml" \
  params_file:="$params" route:="$route" \
  log_directory:="$checkout/results/journal" max_linear:=2.0 autostart:=false
