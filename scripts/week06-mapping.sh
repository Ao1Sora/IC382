#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "$project/scripts/week06-ros.sh" ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/workspace/dev/custom_slam_params_hpc.yaml use_sim_time:=true
