"""Read-only command/encoder capture; does not publish motion."""
import json
import time
from pathlib import Path
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

rclpy.init()
node = rclpy.create_node('ic382_motion_diagnostic')
rows = []
start = time.monotonic()
def command(m):
    rows.append({'t': round(time.monotonic()-start,3), 'kind':'command',
                 'v':m.linear.x, 'w':m.angular.z})
def odom(m):
    rows.append({'t':round(time.monotonic()-start,3), 'kind':'odom',
                 'x':m.pose.pose.position.x,'y':m.pose.pose.position.y,
                 'v':m.twist.twist.linear.x,'w':m.twist.twist.angular.z})
node.create_subscription(Twist, '/cmd_vel', command, 10)
node.create_subscription(Odometry, '/odom', odom, 10)
try:
    while time.monotonic()-start<35:
        rclpy.spin_once(node,timeout_sec=.1)
    path=Path.home()/'.local/state/ic382/motion-diagnostic.json'
    path.write_text(json.dumps(rows))
    commands=[x for x in rows if x['kind']=='command']
    odometry=[x for x in rows if x['kind']=='odom']
    print(json.dumps({'file':str(path),'commands':len(commands),'odom':len(odometry),
          'nonzero_commands':[x for x in commands if abs(x['v'])+abs(x['w'])>.001][:25],
          'peak_command':max([abs(x['v']) for x in commands],default=0),
          'peak_encoder_speed':max([abs(x['v']) for x in odometry],default=0),
          'position_change': [odometry[-1]['x']-odometry[0]['x'],odometry[-1]['y']-odometry[0]['y']] if odometry else None}))
finally:
    node.destroy_node(); rclpy.shutdown()
