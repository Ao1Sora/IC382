#!/usr/bin/env bash
set -euo pipefail
cd /workspace
mkdir -p /tmp/ic382-gdb-download
cd /tmp/ic382-gdb-download
apt-get -o APT::Sandbox::User=root download gdb libdebuginfod1 libipt2 libsource-highlight4v5 libsource-highlight-common libbabeltrace1
for archive in ./*.deb; do dpkg-deb -x "$archive" /; done
cd /workspace/tools/isaacsim-4.5.0
unset DISPLAY WAYLAND_DISPLAY
export ROS_DISTRO=humble
export LD_LIBRARY_PATH="/opt/nvidia/lib:$PWD/exts/isaacsim.ros2.bridge/humble/lib:${LD_LIBRARY_PATH:-}"
export CARB_APP_PATH="$PWD/kit" ISAAC_PATH="$PWD" EXP_PATH="$PWD/apps"
set +u
source ./setup_python_env.sh
set -u
exec gdb --batch -ex 'set pagination off' -ex 'set confirm off' -ex run -ex 'thread apply all bt 5' --args ./kit/python/bin/python3 /workspace/scripts/week06-flat-smoke.py
