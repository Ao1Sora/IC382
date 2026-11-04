#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -o APT::Sandbox::User=root update
apt-get -o APT::Sandbox::User=root install -y ca-certificates curl gnupg locales
locale-gen en_US.UTF-8
export LANG=en_US.UTF-8
curl --fail --location --retry 3 https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main\n' > /etc/apt/sources.list.d/ros2.list
apt-get -o APT::Sandbox::User=root update
apt-get -o APT::Sandbox::User=root install -y ros-humble-ros-base ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-slam-toolbox ros-humble-rviz2 ros-humble-teleop-twist-keyboard python3-pip libgl1 libegl1
set +u
source /opt/ros/humble/setup.bash
set -u
ros2 pkg prefix nav2_bringup
ros2 pkg prefix slam_toolbox
ros2 pkg prefix rviz2
printf 'IC382_WEEK06_ROS_INSTALL_PASSED\n'
