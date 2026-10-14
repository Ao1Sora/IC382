#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
container="$project/tools/ros2-humble-root"
args=(--unshare-user --uid 0 --gid 0 --bind "$container" / --proc /proc --dev-bind /dev /dev --ro-bind /sys /sys --ro-bind /etc/resolv.conf /etc/resolv.conf --bind "$project" /workspace --bind "$project" "$project" --bind "$project/dev" /home/student/dev --bind /tmp /tmp --chdir /workspace --setenv HOME /home/student --setenv LANG en_US.UTF-8)
if [[ -f "$HOME/.Xauthority" ]]; then args+=(--ro-bind "$HOME/.Xauthority" /home/student/.Xauthority); fi
if [[ -d /usr/share/vulkan/icd.d ]]; then args+=(--ro-bind /usr/share/vulkan/icd.d /usr/share/vulkan/icd.d); fi
if [[ -d /usr/share/glvnd/egl_vendor.d ]]; then args+=(--ro-bind /usr/share/glvnd/egl_vendor.d /usr/share/glvnd/egl_vendor.d); fi
for library in /usr/lib64/libnvidia*.so* /usr/lib64/libcuda.so* /usr/lib64/libnvoptix.so* /usr/lib64/libGLX_nvidia.so* /usr/lib64/libEGL_nvidia.so* /usr/lib64/libvdpau_nvidia.so*; do
  [[ -e "$library" ]] || continue
  args+=(--ro-bind "$library" "/opt/nvidia/lib/$(basename "$library")")
done
args+=(--setenv LD_LIBRARY_PATH /opt/nvidia/lib --setenv FASTRTPS_DEFAULT_PROFILES_FILE /workspace/cache/course-dds.xml --setenv ROS_DOMAIN_ID 82 --setenv RMW_IMPLEMENTATION rmw_fastrtps_cpp)
exec bwrap "${args[@]}" /bin/bash "$@"
