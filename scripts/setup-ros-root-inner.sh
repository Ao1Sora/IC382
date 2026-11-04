#!/usr/bin/env bash
set -euo pipefail
mode=${1:?missing mode}
export DEBIAN_FRONTEND=noninteractive
apt-get -o APT::Sandbox::User=root update
apt-get -o APT::Sandbox::User=root install -y ca-certificates curl gnupg locales
locale-gen en_US.UTF-8
curl --fail --location --retry 3 https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main\n' > /etc/apt/sources.list.d/ros2.list
apt-get -o APT::Sandbox::User=root update
apt-get -o APT::Sandbox::User=root install -y python3-pip python3-yaml python3-numpy python3-opencv python3-colcon-common-extensions build-essential cmake libgl1 libegl1 zenity wmctrl
mapfile -t packages < <(sed -n '/^ros-humble-[a-z0-9+.-]*=/p' /workspace/config/hpc-ros-packages-20261104.txt)
(( ${#packages[@]} > 0 )) || { echo 'ROS package manifest is empty' >&2; exit 1; }
if [[ "$mode" == --current ]]; then
  for i in "${!packages[@]}"; do packages[$i]=${packages[$i]%%=*}; done
  echo 'Installing current repository builds: these may differ from HPC.' >&2
fi
apt-get -o APT::Sandbox::User=root install -y "${packages[@]}"
set +u
source /opt/ros/humble/setup.bash
set -u
ros2 pkg prefix nav2_bringup
ros2 pkg prefix slam_toolbox
ros2 pkg prefix rviz2
