#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for attempt in {1..180}; do
  if ! fuser tools/ros2-humble-root/var/lib/dpkg/lock >/dev/null 2>&1; then
    exec ./scripts/week06-ubuntu.sh scripts/week06-configure-inner.sh
  fi
  sleep 5
done
echo 'Package manager is still active; repair not started.' >&2
exit 1
