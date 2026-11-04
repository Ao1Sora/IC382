"""Reproduce the actual 80ms keyboard loop under live ROS message traffic."""
import os,time,threading
from pathlib import Path
from unittest.mock import Mock
assert os.environ.get('ROS_DOMAIN_ID')=='138'
import rclpy
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import PoseWithCovarianceStamped
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from robot_console import Console
rclpy.init();app=Console(Path(__file__).resolve().parents[1],test_mode=True)
backend=rclpy.create_node('console_callback_load_backend');ex=SingleThreadedExecutor();ex.add_node(backend)
pose=backend.create_publisher(PoseWithCovarianceStamped,'/amcl_pose',10)
scan=backend.create_publisher(LaserScan,'/scan',10)
mission=backend.create_publisher(String,'/ic382/mission_status',10)
alignment=backend.create_publisher(String,'/ic382/local_alignment',10)
health={'value':''};sent=[0]
def sensors():
 p=PoseWithCovarianceStamped();p.header.stamp=backend.get_clock().now().to_msg();pose.publish(p)
 s=LaserScan();s.ranges=[1.]*540;scan.publish(s)
def status():
 sent[0]+=1;mission.publish(String(data='{"state":"IDLE","health":"'+health['value']+'"}'))
backend.create_timer(.05,sensors);status_timer=backend.create_timer(.1,status)
backend.create_timer(.5,lambda:alignment.publish(String(data='{"state":"tracking","healthy":true}')))
thread=threading.Thread(target=ex.spin,daemon=True);thread.start()
app.publish_body=lambda:None;app.localization_tick=lambda:None
app.mode='NAVIGATION';app.config['localization']['local_scan_match']=True
try:
 end=time.monotonic()+2
 while time.monotonic()<end:app.spin(.005)
 assert app.navigation_healthy(),'Initial state never healthy'
 handle=Mock();app.point_handle=handle;ages=[];until=time.monotonic()+4
 while time.monotonic()<until:
  time.sleep(.08);app.spin(0.);ages.append(time.monotonic()-app.feedback_at);app.tick()
 cancelled=handle.cancel_goal_async.called
 print('80ms UI loop / 20Hz AMCL + 20Hz scan + 10Hz health: sent',sent[0], 'max received health age',round(max(ages),3),'cancelled',cancelled,flush=True)
 if os.environ.get('EXPECT_STARVATION')=='1':
  assert cancelled,'Old UI starvation not reproduced'
  print('REPRODUCED: healthy backend causes false health-timeout cancellation')
 else:
  assert not cancelled,'Healthy navigation falsely canceled under realistic sensor traffic'
  assert max(ages)<.5,'Health callback still starving'
  health['value']='scan_stale';until=time.monotonic()+2.5
  while time.monotonic()<until:time.sleep(.08);app.spin(0.);app.tick()
  handle.cancel_goal_async.assert_called_once()
  assert 'scan_stale' in app.notice,app.notice
  health['value']='';app.point_handle=None
  until=time.monotonic()+.5
  while time.monotonic()<until:app.spin(.01)
  handle=Mock();app.point_handle=handle;status_timer.cancel();until=time.monotonic()+5.
  while time.monotonic()<until:time.sleep(.08);app.spin(0.);app.tick()
  handle.cancel_goal_async.assert_called_once()
  print('PASS: healthy load does not cancel; real fault and dead health heartbeat still cancel')
finally:
 ex.shutdown();thread.join(timeout=3);backend.destroy_node();app.node.destroy_node();rclpy.shutdown()
