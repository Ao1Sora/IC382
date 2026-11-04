"""Motion assistance must keep AMCL running, preserve stop and enforce lower caps."""
from pathlib import Path
import tempfile
import time
from unittest.mock import Mock, patch
from rclpy.task import Future
from sensor_msgs.msg import LaserScan
import rclpy
from geometry_msgs.msg import Twist
from robot_console import Console
from map_catalog import write_config

rclpy.init()
try:
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        map_path=root/'map.yaml';map_path.write_text('image: map.pgm\n')
        write_config(root/'ros2_ws/src/ic382_navigation/config/physical_runtime.yaml',
                     dict(map=str(map_path),navigation_map='',inspection={'desks':[]}))
        app=Console(root,test_mode=True)
        commands=[]
        app.start=lambda name, command:commands.append((name,command))
        app.open_rviz=lambda:None
        app.pub=Mock()
        app.key('G')
        assert app.mode=='LOCALIZATION' and [name for name,_ in commands]==['lidar','localization']
        app.key('i');assert app.x==0., 'Wait for AMCL before moving'
        app.localization_active=True;app.global_requested=False
        app.speed=1.;app.turn=3.
        app.key('o');assert app.x==.05 and app.w==-.15
        app.tick()
        assert app.pub.publish.call_args.args[0].linear.x==.05
        assert app.mode=='LOCALIZATION' and len(commands)==2
        app.key(' ');app.tick()
        assert app.pub.publish.call_args.args[0].linear.x==0.
        assert app.mode=='LOCALIZATION', 'Parking must not terminate AMCL'
        app.key('j');app.tick()
        assert app.pub.publish.call_args.args[0].angular.z==.15
        app.last_move=time.monotonic()-1
        app.tick();assert app.pub.publish.call_args.args[0].angular.z==0., 'Input timeout failed'
        app.key('i');app.localization_active=False;app.tick()
        assert app.pub.publish.call_args.args[0].linear.x==0., 'AMCL inactive must stop assist'
        app.localization_active=True;app.global_requested=False
        app.localization_pending=False;app.localization_call=None
        app.localization_poll=0.;app.amcl_state=Mock()
        app.amcl_state.service_is_ready.return_value=False
        app.nomotion=Mock();app.nomotion.service_is_ready.return_value=True
        completed=Future();completed.set_result(None)
        app.nomotion.call_async.return_value=completed
        scan=LaserScan();scan.ranges=[1.];scan.header.stamp.sec=1
        with patch('robot_console.time.monotonic',return_value=100.):
            app.localization_scan(scan);app.localization_tick()
        assert app.nomotion.call_async.call_count==1
        scan.header.stamp.sec=2
        with patch('robot_console.time.monotonic',return_value=100.5):
            app.localization_scan(scan);app.localization_tick()
        assert app.nomotion.call_async.call_count==1, 'More than one request per second'
        with patch('robot_console.time.monotonic',return_value=101.01):
            app.localization_tick()
        assert app.nomotion.call_async.call_count==2, 'New scan must trigger while rotating'
        with patch('robot_console.time.monotonic',return_value=102.1):
            app.localization_tick()
        assert app.nomotion.call_async.call_count==2, 'Do not reuse old scan'
        pending=Future();app.localization_call=pending
        scan.header.stamp.sec=3
        with patch('robot_console.time.monotonic',return_value=103.2):
            app.localization_scan(scan);app.localization_tick()
        assert app.nomotion.call_async.call_count==2, 'Do not overlap pending requests'
        app.key('X');assert app.mode=='MANUAL' 
        app.node.destroy_node()
        print('PASS: only AMCL, ready gate, assist speed caps, AMCL retained on parking, timeout, inactive stop, exit')
finally:rclpy.shutdown()
