#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
archive=downloads/isaac-sim-standalone-4.5.0-linux-x86_64.zip
curl --fail --location --retry 3 --connect-timeout 20 --continue-at - --output "$archive" https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-4.5.0-linux-x86_64.zip
unzip -tq "$archive"
sha256sum "$archive" > logs/isaacsim-archive.sha256
mkdir -p tools/isaacsim-4.5.0
unzip -q -o "$archive" -d tools/isaacsim-4.5.0
printf 'EXTRACTED\n' > logs/install-state.txt
