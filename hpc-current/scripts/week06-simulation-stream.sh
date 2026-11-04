#!/usr/bin/env bash
set -euo pipefail
cd /workspace/tools/isaacsim-4.5.0
unset DISPLAY WAYLAND_DISPLAY
export ROS_DISTRO=humble RESOURCE_NAME=IsaacSim
export LD_LIBRARY_PATH="/opt/nvidia/lib:$PWD/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH:-}"
exec ./isaac-sim.streaming.sh --/app/extensions/registryEnabled=false --/persistent/isaac/asset_root/default=/workspace/dev/Collected_final_wheeltec_with_scene --/app/window/width=1920 --/app/window/height=1080 --/plugins/carb.tasking.plugin/threadCount=6 --/plugins/omni.tbb.globalcontrol/maxThreadCount=6 --exec /workspace/scripts/course_scene.py
