#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
unset DISPLAY WAYLAND_DISPLAY
export ROS_DISTRO=humble RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DOMAIN_ID=82
export LD_LIBRARY_PATH="$PWD/tools/cpp-runtime/lib:$PWD/tools/isaacsim-4.5.0/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH:-}"
exec ./scripts/isaac-python.sh "$PWD/scripts/week06-bridge-test.py"
