#!/usr/bin/env bash
# Course Jetson workflow. Manual drive and autonomous navigation are separate modes.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode=${1:-manual}
if (($#)); then shift; fi
set +u
source /opt/ros/humble/setup.bash
if [[ -f "$HOME/wheeltec_ros2/install/setup.bash" ]]; then
  source "$HOME/wheeltec_ros2/install/setup.bash"
fi
if [[ -f "$root/ros2_ws/install/setup.bash" ]]; then source "$root/ros2_ws/install/setup.bash"; fi
set -u
case "$mode" in
  build)
    cd "$root/ros2_ws"
    exec colcon build --symlink-install --packages-select turn_on_wheeltec_robot wheeltec_robot_keyboard wheeltec_slam_toolbox wheeltec_nav2 wheeltec_robot_urdf wheeltec_rviz2 wheeltec_radar ic382_interfaces ic382_planners ic382_navigation "$@"
    ;;
  test) exec python3 "$root/scripts/check_navigation.py" "$@" ;;
  manual|drive|console) exec python3 "$root/scripts/robot_console.py" "$@" ;;
  map) exec ros2 launch ic382_navigation mapping.launch.py "$@" ;;
  teleop) exec ros2 run wheeltec_robot_keyboard wheeltec_keyboard "$@" ;;
  save-map) exec ros2 launch wheeltec_nav2 save_map.launch.py "$@" ;;
  navigate) exec ros2 launch ic382_navigation navigation.launch.py "config_file:=$root/ros2_ws/src/ic382_navigation/config/physical_runtime.yaml" "$@" ;;
  *) printf '%s\n' 'Usage: bash run.sh {console|manual|drive|build|test|map|teleop|save-map|navigate} [arguments]' ;;
esac
