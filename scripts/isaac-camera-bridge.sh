#!/usr/bin/env bash
# Run on the HPC host while the course simulation is running. The simulation
# loop picks up logs/course601-runtime-request.py and executes it once.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="${IC382_PROJECT:-$(cd "$here/../.." && pwd)}"
target="$project/logs/course601-runtime-request.py"
[[ -d "$project/logs" ]] || { echo "Missing simulation logs directory: $project/logs"; exit 1; }
cp "$here/isaac-camera-bridge-hook.py" "$target"
echo "Camera bridge request queued: $target"
echo "Verify inside ROS: ros2 topic hz /camera/color/image_raw"
