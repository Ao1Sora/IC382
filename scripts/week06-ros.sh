#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "$project/scripts/week06-ubuntu.sh" -c 'source /opt/ros/humble/setup.bash; export LD_LIBRARY_PATH=/opt/nvidia/lib:$LD_LIBRARY_PATH; exec "$@"' -- "$@"
