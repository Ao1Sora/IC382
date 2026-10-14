#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
root="$project/tools/ros2-humble-root"
isaac="$project/tools/isaacsim-4.5.0"
cd "$isaac"
unset DISPLAY WAYLAND_DISPLAY
export RESOURCE_NAME=IsaacSim ROS_DISTRO=humble
export LD_LIBRARY_PATH="$project/tools/cpp-runtime/lib:$isaac/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH:-}"
loader="$root/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
libpath="$root/lib/x86_64-linux-gnu:$root/usr/lib/x86_64-linux-gnu:$project/tools/cpp-runtime/lib:$isaac/kit/lib:$isaac/exts/isaacsim.ros2.bridge/humble/lib:/usr/lib64"
exec "$isaac/kit/.kit-course" "$isaac/apps/isaacsim.exp.full.streaming.kit" --ext-folder "$isaac/apps" --no-window --/app/window/width=1280 --/app/window/height=720 --/plugins/carb.tasking.plugin/threadCount=6 --/plugins/omni.tbb.globalcontrol/maxThreadCount=6 --exec "$project/scripts/course_scene_host.py"
