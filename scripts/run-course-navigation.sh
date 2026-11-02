#!/usr/bin/env bash
# Runs inside the HPC simulation's existing ROS container/network namespace.
set -eo pipefail
checkout=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$checkout/ros2_ws/install/setup.bash"
exec ros2 launch ic382_navigation simulation.launch.py \
  config_file:="$checkout/simulation/config/runtime.yaml" "$@"
