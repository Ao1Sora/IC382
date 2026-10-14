#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "$project/scripts/week06-ros.sh" ros2 run tf2_ros static_transform_publisher --x -1.189 --y 0.0 --z -0.38 --frame-id base_link --child-frame-id base_footprint
