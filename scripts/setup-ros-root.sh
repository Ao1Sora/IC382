#!/usr/bin/env bash
# Build a separate user-owned Ubuntu rootfs. Never alters an existing one.
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:---exact}
[[ "$mode" == --exact || "$mode" == --current ]] || { echo 'Usage: setup-ros-root.sh [--exact|--current]' >&2; exit 2; }
root="$project/tools/ros2-humble-root"
[[ ! -e "$root" ]] || { echo "Already exists: $root (refusing to overwrite)" >&2; exit 1; }
for cmd in bwrap curl tar sha256sum; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }; done
mkdir -p "$project/tools" "$project/cache"
archive="$project/cache/ubuntu-jammy-20240613-root.tar.xz"
url=https://cloud-images.ubuntu.com/minimal/releases/jammy/release-20240613/ubuntu-22.04-minimal-cloudimg-amd64-root.tar.xz
[[ -f "$archive" ]] || curl --fail --silent --show-error --location --retry 3 "$url" -o "$archive"
echo "2bf9b7c7ab6d73a52000619e1550089191835d2cf4924ae13d8a51453b54fed0  $archive" | sha256sum -c -
mkdir "$root"
tar --extract --xz --file "$archive" --directory "$root" --no-same-owner --no-same-permissions --exclude='./dev/*' --exclude='dev/*'
mkdir -p "$root/workspace" "$root/proc" "$root/dev" "$root/tmp" "$root/home/student/dev" "$root/opt/nvidia/lib"
# Cloud images use a dangling systemd-resolved symlink in containers.
if [[ -L "$root/etc/resolv.conf" ]]; then rm "$root/etc/resolv.conf"; fi
touch "$root/etc/resolv.conf"
echo "Installing packages in $root; mode=$mode"
bwrap --unshare-user --uid 0 --gid 0 --bind "$root" / --proc /proc --dev /dev \
  --ro-bind /etc/resolv.conf /etc/resolv.conf --bind "$project" /workspace \
  --chdir /workspace --setenv DEBIAN_FRONTEND noninteractive \
  /bin/bash /workspace/scripts/setup-ros-root-inner.sh "$mode"
echo 'ROS rootfs installation complete.'
