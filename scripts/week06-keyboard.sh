#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "$project/scripts/week06-ros.sh" ros2 run teleop_twist_keyboard teleop_twist_keyboard
