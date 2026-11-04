"""PTY + real ROS test, remapped away from the physical chassis."""
import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import termios
import time
import rclpy
from geometry_msgs.msg import Twist

rclpy.init()
node = rclpy.create_node('keyboard_check')
samples = []
sub = node.create_subscription(Twist, '/ic382/test_keyboard_only',
    lambda m: samples.append((m.linear.x, m.linear.y, m.angular.z)), 10)
master, slave = pty.openpty()
settings = termios.tcgetattr(slave)
log = open('/tmp/ic382-keyboard-check.log', 'w')
proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('robot_console.py')), '--test-mode',
    '--ros-args', '-r', 'cmd_vel:=/ic382/test_keyboard_only'],
    stdin=slave, stdout=log, stderr=log, start_new_session=True)
def spin(seconds):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.02)
def key(value):
    os.write(master, value.encode())
    spin(0.14)
try:
    deadline = time.monotonic()+10
    while not samples and time.monotonic()<deadline:
        spin(0.1)
    assert samples, 'No ROS messages'
    key('i')
    assert samples[-1][0] > 0, samples[-1]
    spin(0.8)
    assert samples[-1] == (0.,0.,0.), 'Input timeout failed'
    for _ in range(24): key('q')
    key('o')
    assert 0 < samples[-1][0] <= .1 and -.3 <= samples[-1][2] < 0
    key('k')
    assert samples[-1] == (0.,0.,0.), 'Stop failed'
    key('b'); key('j')
    assert samples[-1][1] > 0 and samples[-1][2] == 0
    key(' ')
    assert samples[-1] == (0.,0.,0.), 'Omni stop failed'
    key('i')
    proc.send_signal(signal.SIGTERM)
    spin(0.5)
    proc.wait(timeout=5)
    assert proc.returncode == 0
    assert samples[-1] == (0.,0.,0.), 'Exit stop failed'
    assert termios.tcgetattr(slave) == settings, 'Terminal not restored'
    print('PASS: unified main UI, forward, timeout, speed caps, turn, k/space, omni, SIGTERM stop, terminal restore')
finally:
    if proc.poll() is None: proc.kill(); proc.wait()
    os.close(master); os.close(slave); log.close()
    node.destroy_node(); rclpy.shutdown()
