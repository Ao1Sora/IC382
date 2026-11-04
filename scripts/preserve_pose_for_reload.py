#!/usr/bin/env python3
"""Preserve the existing operator-established pose across a stopped stack reload."""
import argparse
import json
import math
from pathlib import Path
import time
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import Buffer,TransformListener


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['capture','restore'])
    mode=parser.parse_args().mode
    target=Path.home()/'.local/state/ic382/pose-before-local-reload.json'
    rclpy.init();node=rclpy.create_node('preserve_pose_for_reload')
    try:
        if mode=='capture':
            buffer=Buffer();listener=TransformListener(buffer,node);commands=[]
            node.create_subscription(Twist,'/cmd_vel',lambda m:commands.append(m),qos_profile_sensor_data)
            until=time.monotonic()+3
            while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.03)
            assert len(commands)>=5 and all(abs(m.linear.x)+abs(m.linear.y)+abs(m.angular.z)<.001 for m in commands[-10:]),'Robot must be stopped before preserving pose'
            transform=buffer.lookup_transform('map','base_footprint',rclpy.time.Time())
            t,q=transform.transform.translation,transform.transform.rotation
            pose=dict(x=t.x,y=t.y,z=q.z,w=q.w,captured_at=time.time())
            target.write_text(json.dumps(pose));print('Preserved current pose:',pose)
        else:
            pose=json.loads(target.read_text());assert time.time()-pose['captured_at']<180,'Saved pose too old'
            seen=[]
            node.create_subscription(PoseWithCovarianceStamped,'/initialpose',lambda m:seen.append(m),10)
            publisher=node.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
            until=time.monotonic()+40
            while time.monotonic()<until:
                rclpy.spin_once(node,timeout_sec=.05)
                names={p.node_name for p in node.get_subscriptions_info_by_topic('/initialpose')}
                if {'amcl','local_alignment'}<=names:break
            else:raise RuntimeError('AMCL and local refinement did not become ready')
            if seen:
                print('Operator provided a new initial pose; saved pose was not restored');return
            message=PoseWithCovarianceStamped();message.header.frame_id='map';message.header.stamp=node.get_clock().now().to_msg()
            message.pose.pose.position.x=pose['x'];message.pose.pose.position.y=pose['y']
            message.pose.pose.orientation.z=pose['z'];message.pose.pose.orientation.w=pose['w']
            message.pose.covariance[0]=message.pose.covariance[7]=.03**2
            message.pose.covariance[35]=math.radians(1.)**2
            publisher.publish(message)
            until=time.monotonic()+.7
            while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.03)
            print('Restored existing pose estimate; no global alignment performed')
    finally:
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
