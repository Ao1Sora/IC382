#!/usr/bin/env bash
set -euo pipefail
cd /workspace
unset DISPLAY WAYLAND_DISPLAY
exec ./scripts/isaac-python.sh /workspace/scripts/week06-clean-scene.py
