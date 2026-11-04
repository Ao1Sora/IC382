#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
checkout="$project/robot-ros2"
commit=a0ab04797c2fb96e29c9eea2905208355fbf669a
[[ ! -e "$checkout" ]] || { echo "Already exists: $checkout (refusing to overwrite)" >&2; exit 1; }
git clone --branch robot-ros2 https://github.com/Ao1Sora/IC382.git "$checkout"
git -C "$checkout" merge-base --is-ancestor "$commit" HEAD || { echo 'Pinned commit not in branch history' >&2; exit 1; }
git -C "$checkout" switch --detach "$commit"
git -C "$checkout" switch -C robot-ros2
echo "Robot checkout at $commit; build it with the commands in DEPLOYMENT.md."
