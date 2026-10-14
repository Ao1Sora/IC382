#!/usr/bin/env bash
set -euo pipefail
cd /workspace
unset DISPLAY WAYLAND_DISPLAY
export ROS_DISTRO=humble
export LD_LIBRARY_PATH="/opt/nvidia/lib:$PWD/tools/isaacsim-4.5.0/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH:-}"
exec ./scripts/isaac-python.sh /workspace/scripts/week06-ready-test.py
