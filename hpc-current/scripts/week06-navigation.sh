#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f "$project/dev/map/my_map.yaml" ]] || { echo 'Create and save a map first.' >&2; exit 1; }
exec "$project/scripts/week06-ros.sh" ros2 launch nav2_bringup bringup_launch.py use_sim_time:=true map:=/workspace/dev/map/my_map.yaml params_file:=/workspace/dev/custom_nav2_params_hpc.yaml
