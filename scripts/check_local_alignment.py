#!/usr/bin/env python3
"""Exercise manual-start + small refinement using synthetic room scans in domain 138."""
import math
import os
import signal
import subprocess
import tempfile
import time
assert os.environ.get('ROS_DOMAIN_ID')=='138'
import rclpy
from rclpy.duration import Duration
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped,TransformStamped
from nav_msgs.msg import OccupancyGrid,Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster,StaticTransformBroadcaster
import json
from pathlib import Path
from unittest.mock import Mock
from robot_console import Console


def main():
    rclpy.init();node=rclpy.create_node('synthetic_local_alignment_backend')
    tf=TransformBroadcaster(node);static=StaticTransformBroadcaster(node)
    laser=TransformStamped();laser.header.frame_id='base_footprint';laser.child_frame_id='laser'
    laser.transform.rotation.w=1.;static.sendTransform(laser)
    poses=[];statuses=[];estimate=[.025,-.015,math.radians(.75)];turn_start=None;tf_delay=.12
    app=Console(Path(__file__).resolve().parents[1],test_mode=True)
    app.mode='NAVIGATION';app.config['localization']['local_scan_match']=True
    app.publish_body=lambda:None;app.localization_tick=lambda:None
    handle=None
    def truth(t):return 0. if turn_start is None else max(0.,t-turn_start)*.15
    def pose(msg):
        poses.append(msg);p=msg.pose.pose
        estimate[:]=[p.position.x,p.position.y,2*math.atan2(p.orientation.z,p.orientation.w)-truth(node.get_clock().now().nanoseconds/1e9)]
    node.create_subscription(PoseWithCovarianceStamped,'/initialpose',pose,10)
    node.create_subscription(String,'/ic382/local_alignment',lambda m:statuses.append(json.loads(m.data)),10)
    pose_pub=node.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
    scans=node.create_publisher(LaserScan,'/scan',10)
    odoms=node.create_publisher(Odometry,'/odom_combined',10)
    maps=node.create_publisher(OccupancyGrid,'/map',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    grid=OccupancyGrid();grid.header.frame_id='map';grid.info.resolution=.05
    grid.info.width=grid.info.height=200;grid.info.origin.position.x=grid.info.origin.position.y=-5.
    grid.info.origin.orientation.w=1.;grid.data=[0]*40000
    for y in range(200):
        for x in range(200):
            if y in (60,140) or x in (40,160):grid.data[y*200+x]=100
    maps.publish(grid)
    scan=LaserScan();scan.header.frame_id='laser';scan.angle_min=-math.pi
    scan.angle_increment=2*math.pi/360;scan.range_min=.05;scan.range_max=6.
    scan.ranges=[]
    for i in range(360):
        a=scan.angle_min+i*scan.angle_increment;c,s=math.cos(a),math.sin(a)
        candidates=[]
        if abs(c)>1e-8:candidates.append((3.025 if c>0 else -2.975)/c)
        if abs(s)>1e-8:candidates.append((2.025 if s>0 else -1.975)/s)
        scan.ranges.append(float(min(candidates)))
    def publish():
        now=node.get_clock().now();t=now.nanoseconds/1e9
        # Deliberately delayed odom TF, with a fresh scan ahead of it.
        stamp=now-Duration(seconds=tf_delay)
        m=TransformStamped();m.header.stamp=stamp.to_msg()
        m.header.frame_id='map';m.child_frame_id='odom_combined'
        m.transform.translation.x=estimate[0];m.transform.translation.y=estimate[1]
        m.transform.rotation.z=math.sin(estimate[2]/2);m.transform.rotation.w=math.cos(estimate[2]/2)
        b=TransformStamped();b.header.stamp=stamp.to_msg()
        b.header.frame_id='odom_combined';b.child_frame_id='base_footprint'
        a=truth(stamp.nanoseconds/1e9)
        b.transform.rotation.z=math.sin(a/2);b.transform.rotation.w=math.cos(a/2)
        tf.sendTransform([m,b])
        odom=Odometry();odom.header.frame_id='odom_combined';odom.child_frame_id='base_footprint'
        odom.header.stamp=stamp.to_msg();odom.twist.twist.angular.z=.15 if turn_start else 0.
        odoms.publish(odom)
        scan.header.stamp=(now-Duration(seconds=.02)).to_msg()
        scan.ranges=[]
        for i in range(360):
            a=scan.angle_min+i*scan.angle_increment+truth(t-.02);c,s=math.cos(a),math.sin(a)
            candidates=[]
            if abs(c)>1e-8:candidates.append((3.025 if c>0 else -2.975)/c)
            if abs(s)>1e-8:candidates.append((2.025 if s>0 else -1.975)/s)
            scan.ranges.append(float(min(candidates)))
        scans.publish(scan)
    node.create_timer(.05,publish)
    log=tempfile.TemporaryFile(mode='w+')
    process=subprocess.Popen(['ros2','run','ic382_navigation','local_alignment'],stdout=log,stderr=log,start_new_session=True)
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.025)
            rclpy.spin_once(app.node,timeout_sec=0.)
            if handle is not None:
                app.feedback={'state':'IDLE','health':''};app.feedback_at=time.monotonic()
                app.tick()
    try:
        spin(7.)
        assert not poses,'Corrected before operator set initial pose'
        assert any(s['state']=='set_2d_pose_estimate_first' for s in statuses),(statuses,process.poll())
        manual=PoseWithCovarianceStamped();manual.header.frame_id='map';manual.header.stamp=node.get_clock().now().to_msg()
        manual.pose.pose.position.x=estimate[0];manual.pose.pose.position.y=estimate[1]
        manual.pose.pose.orientation.z=math.sin(estimate[2]/2);manual.pose.pose.orientation.w=math.cos(estimate[2]/2)
        pose_pub.publish(manual)
        spin(8.)
        assert len(poses)>1,('No local refinement after manual initial pose',statuses[-8:])
        for before,after in zip(poses,poses[1:]):
            a,b=before.pose.pose,after.pose.pose
            assert math.hypot(a.position.x-b.position.x,a.position.y-b.position.y)<=.0601
            angle=2*math.atan2(b.orientation.z,b.orientation.w)-2*math.atan2(a.orientation.z,a.orientation.w)
            assert abs(angle)<=math.radians(4.001)
        assert any(s['healthy'] for s in statuses)
        assert any(s.get('synchronized_scan_delay_ms',0.)>=80 for s in statuses), 'Delayed TF stream was not exercised'
        assert math.hypot(estimate[0],estimate[1])<math.hypot(.025,.015)
        # Duplicate launch must fail before creating a second ROS publisher.
        duplicate=subprocess.Popen(['ros2','run','ic382_navigation','local_alignment'],stdout=log,stderr=log,start_new_session=True)
        try:
            spin(3.)
            assert duplicate.poll() is not None and duplicate.returncode!=0,'Duplicate alignment instance accepted'
        finally:
            if duplicate.poll() is None:
                os.killpg(duplicate.pid,signal.SIGINT);duplicate.wait(timeout=5)
        assert len(node.get_publishers_info_by_topic('/ic382/local_alignment'))==1
        handle=Mock();app.point_handle=handle
        # Start with a four-degree bias, outside the previous two-degree window.
        estimate[2]=math.radians(4.)
        turn_start=node.get_clock().now().nanoseconds/1e9
        statuses.clear();count=len(poses)
        spin(9.)
        assert len(poses)>count,'No corrections during turning'
        assert abs(estimate[2])<math.radians(.8),('Turning timestamp regression',estimate)
        assert any(s.get('motion_compensation_s',0.)>.10 for s in statuses)
        assert not any(s['state']=='motion_compensation_unavailable' for s in statuses),statuses
        assert all(s['healthy'] for s in statuses),statuses
        handle.cancel_goal_async.assert_not_called()
        # A temporarily withheld correction must not cancel a healthy goal.
        tf_delay=.30;estimate[2]=math.radians(2.);statuses.clear();count=len(poses)
        spin(4.)
        withheld=[s for s in statuses if s['state']=='motion_compensation_unavailable']
        assert withheld and all(s['healthy'] for s in withheld),statuses
        assert len(poses)==count,'Applied a correction despite stale compensation TF'
        handle.cancel_goal_async.assert_not_called()
        tf_delay=.12;statuses.clear();spin(5.)
        assert len(poses)>count and abs(estimate[2])<math.radians(.8)
        handle.cancel_goal_async.assert_not_called()
        # Actual manual reset and a genuinely unhealthy status still cancel.
        manual.header.stamp=node.get_clock().now().to_msg();pose_pub.publish(manual)
        spin(1.5)
        handle.cancel_goal_async.assert_called_once()
        print('PASS: singleton, continuous turning corrections + real console navigation gate, withheld correction does not cancel, manual reset cancels')
        print('Final estimate:',estimate,'correction count:',len(poses)-1)
    finally:
        os.killpg(process.pid,signal.SIGINT)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        log.seek(0);print(log.read()[-1800:]);log.close()
        app.node.destroy_node();node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
