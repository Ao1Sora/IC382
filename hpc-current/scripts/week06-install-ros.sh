#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec bwrap --unshare-user --uid 0 --gid 0 --bind "$project/tools/ros2-humble-root" / --proc /proc --dev /dev --ro-bind /etc/resolv.conf /etc/resolv.conf --bind "$project" /workspace --chdir /workspace /bin/bash scripts/week06-ros-install-inner.sh
