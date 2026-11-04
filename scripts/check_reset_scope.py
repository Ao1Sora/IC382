"""Ensure reset matches the robot stack without sweeping unrelated Python/SSH/VNC."""
from reset_robot import ROOT, is_robot_command, snapshot

assert is_robot_command(['python3', str(ROOT/'scripts/robot_console.py')])
assert is_robot_command(['/usr/bin/python3','/opt/ros/humble/bin/ros2','launch',
                         'turn_on_wheeltec_robot','turn_on_wheeltec_robot.launch.py'])
assert is_robot_command(['/opt/ros/humble/bin/ros2','launch',str(ROOT/'scripts/localization_only.launch.py'), 'config_file:=x'])
assert is_robot_command([str(ROOT/'ros2_ws/install/turn_on_wheeltec_robot/lib/turn_on_wheeltec_robot/wheeltec_robot_node')])
assert is_robot_command(['/opt/ros/humble/lib/rviz2/rviz2','-d',str(ROOT/'scripts/robot_navigation.rviz')])
for command in (['python3','/usr/local/bin/jupyter-lab'], ['/usr/sbin/sshd','-D'],
                ['/usr/bin/x11vnc','-display',':0'], ['python3',str(ROOT/'scripts/reset_robot.py')],
                ['python3','/home/other/robot_console.py'], ['python3','unrelated.py'],
                ['/opt/ros/humble/bin/ros2','launch','unrelated_package','test.launch.py']):
    assert not is_robot_command(command), command
assert snapshot(), 'Linux process inventory must be readable'
print('PASS: robot-only scope; SSH/VNC/Jupyter/reset/unrelated Python excluded')
