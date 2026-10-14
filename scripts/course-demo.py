#!/usr/bin/env python3
import argparse,time,json,math
from pathlib import Path
import rclpy
from geometry_msgs.msg import Twist
from rclpy.signals import SignalHandlerOptions
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
rclpy.init(signal_handler_options=SignalHandlerOptions.NO);node=rclpy.create_node('ic382_simple_demo');pub=node.create_publisher(Twist,'/cmd_vel',10)
def drive(v,w,seconds):
 end=time.monotonic()+seconds;msg=Twist();msg.linear.x=float(v);msg.angular.z=float(w)
 while time.monotonic()<end:
  pub.publish(msg);rclpy.spin_once(node,timeout_sec=0.05)
try:
 end=time.monotonic()+8
 while pub.get_subscription_count()==0 and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
 if pub.get_subscription_count()==0:raise RuntimeError('No simulation cmd_vel subscriber. Start simulation first.')
 print('ROS2 control connected.',flush=True)
 if args.check:
  drive(0.,0.,1.)
 else:
  for label,v,w,duration in [('Forward 2 m',.5,0.,4.),('Backward 2 m',-.5,0.,4.),('Turn left 90 degrees',0.,.5,3.14),('Turn right 90 degrees',0.,-.5,3.14)]:
   before=json.loads(Path('/workspace/logs/week06-live.json').read_text())
   print(label,flush=True);drive(v,w,duration);drive(0.,0.,1.2)
   after=json.loads(Path('/workspace/logs/week06-live.json').read_text())
   distance=math.dist(before['world_pose'][:2],after['world_pose'][:2])
   def yaw(q):
    w,x,y,z=q;return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
   angle=yaw(after['world_orientation'])-yaw(before['world_orientation']);angle=math.atan2(math.sin(angle),math.cos(angle))
   print(f'Actual movement: {distance:.2f} m; rotation: {math.degrees(angle):.1f} degrees',flush=True)
except KeyboardInterrupt:print('Interrupted; stopping.',flush=True)
finally:
 drive(0.,0.,.8);node.destroy_node();rclpy.shutdown()
print('Demo finished; robot stopped.',flush=True)
