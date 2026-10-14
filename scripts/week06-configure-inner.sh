#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive FAKEROOTDONTTRYCHOWN=1
mkdir -p /tmp/ic382-fakeroot-download
cd /tmp/ic382-fakeroot-download
apt-get -o APT::Sandbox::User=root download fakeroot libfakeroot
for archive in ./*.deb; do dpkg-deb -x "$archive" /; done
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d
fakeroot dpkg --configure -a || true
fakeroot apt-get -o APT::Sandbox::User=root --no-install-recommends -f install -y
set +u
source /opt/ros/humble/setup.bash
set -u
ros2 pkg prefix nav2_bringup
ros2 pkg prefix slam_toolbox
ros2 pkg prefix rviz2
python3 -c 'import rclpy; from sensor_msgs.msg import LaserScan; from nav2_msgs.action import NavigateToPose; print("IC382_WEEK06_ROS_INSTALL_PASSED")'
