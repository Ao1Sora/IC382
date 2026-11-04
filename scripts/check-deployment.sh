#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project"
failed=0
check_file() { [[ -f "$1" ]] || { echo "MISSING: $1"; failed=1; }; }
check_hash() {
 if [[ ! -f "$2" ]]; then echo "MISSING: $2"; failed=1
 elif ! printf '%s  %s\n' "$1" "$2" | sha256sum -c --status; then echo "MISMATCH or LFS pointer: $2"; failed=1
 else echo "OK: $2"; fi
}
check_hash 9ede2cc2dd6e74e1a8220230509f8b2bf78b1c49cba46a665e1668edfbab754f robots/team_robot_20261013/team_robot.usdc
check_hash 06792940a8e17706a6a55aa7eb77fb32f8ced521a1261d4d4b3cf4c42dcaa620 robots/team_robot_20261013/team_robot_scene.usdc
check_hash 5493c876e6ba5d77764987f2833a2b27462c90500e3c399989cb808d27d630d1 dev/Collected_final_wheeltec_with_scene/final_wheeltec_hpc45_clean.usdc
check_hash 027281fbdb929510d9228accc850e136ebe49ad43cfdc1dfc4b9bf5aceb2fd7f dev/Collected_final_wheeltec_with_scene/course-original-lidar.usda
check_file tools/isaacsim-6.0.1/VERSION
check_file tools/ros2-humble-root/opt/ros/humble/setup.bash
check_file tools/rtx-cuda-proxy.so
check_file tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/ptxas
check_file tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/nvlink
check_file 'tools/webrtc-client-2.0.0/opt/Isaac Sim WebRTC Streaming Client/isaacsim-webrtc-streaming-client'
check_file robot-ros2/ros2_ws/install/setup.bash
if [[ -f tools/isaacsim-6.0.1/VERSION ]] && ! grep -q '^6\.0\.1-' tools/isaacsim-6.0.1/VERSION; then echo 'Unexpected Isaac Sim version'; failed=1; fi
if [[ -d robot-ros2/.git ]]; then
 actual=$(git -C robot-ros2 rev-parse HEAD)
 [[ "$actual" == a0ab04797c2fb96e29c9eea2905208355fbf669a ]] || { echo "Unexpected robot commit: $actual"; failed=1; }
else echo 'MISSING: robot-ros2 Git checkout'; failed=1; fi
(( failed == 0 )) || { echo 'Deployment is incomplete; see DEPLOYMENT.md.' >&2; exit 1; }
echo 'Required files are present. This does not replace a GPU runtime test.'
