#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$project/dev/map"
exec "$project/scripts/week06-ros.sh" ros2 run nav2_map_server map_saver_cli -f /workspace/dev/map/my_map --ros-args -p use_sim_time:=true
