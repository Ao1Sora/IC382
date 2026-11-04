#!/usr/bin/env bash
# Load robot code from the robot-ros2 checkout; never start the course Nav2.
set -euo pipefail
project=$(realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)")
checkout=$(realpath "${IC382_ROBOT_CHECKOUT:-$project/robot-ros2}")
relative=${checkout#"$project/"}
[[ "$relative" != "$checkout" && "$relative" != ../* ]] || { echo 'Robot checkout must be inside the simulation project'; exit 1; }
branch=$(git -C "$checkout" symbolic-ref --short HEAD)
[[ "$branch" == robot-ros2 ]] || { echo "Expected robot-ros2 branch, found $branch"; exit 1; }
[[ -f "$checkout/ros2_ws/install/setup.bash" ]] || { echo "Build $checkout/ros2_ws first"; exit 1; }
echo "Robot checkout: $checkout branch=$branch commit=$(git -C "$checkout" rev-parse --short HEAD)"
if [[ "${1:-}" == --check ]]; then exit 0; fi
mkdir -p "$project/cache"
exec flock -n "$project/cache/navigation-mvp.lock" \
  "$project/scripts/week06-ros.sh" bash "/workspace/$relative/scripts/run-course-navigation.sh" "$@"
