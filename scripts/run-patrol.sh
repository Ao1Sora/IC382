#!/usr/bin/env bash
set -euo pipefail
checkout=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ $# -ge 3 ]] || { echo 'Usage: run-patrol.sh MAP_YAML NAV2_PARAMS_YAML ROUTE_YAML [launch arguments]'; exit 1; }
map=$1;params=$2;route=$3;shift 3
set +u
source /opt/ros/humble/setup.bash
source "$checkout/ros2_ws/install/setup.bash"
set -u
exec ros2 launch ic382_navigation patrol.launch.py map:="$map" params_file:="$params" route:="$route" "$@"
