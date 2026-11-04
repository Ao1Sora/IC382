"""One-Hz local scan refinement. Never performs global search or drives the robot."""
import json
import math
import time
import os
import fcntl
from pathlib import Path
from collections import deque
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener
from .local_scan_match import LocalScanMatcher, alignment_supports_navigation, propagate_pose


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


class LocalAlignment(Node):
    def __init__(self):
        super().__init__('local_alignment')
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.matcher=None;self.scan=None;self.scan_at=-math.inf;self.used=None
        self.scans=deque(maxlen=30)
        self.manual_ready=False;self.manual_at=-math.inf;self.own_stamp=None
        self.good_once=False;self.bad_count=0
        self.odom=None;self.odom_at=-math.inf
        self.odom_frame=self.declare_parameter('odom_frame','odom_combined').value
        self.pose_pub=self.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
        self.status=self.create_publisher(String,'/ic382/local_alignment',10)
        self.create_subscription(OccupancyGrid,'/map',self.map,
            QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(LaserScan,'/scan',self.receive_scan,qos_profile_sensor_data)
        self.create_subscription(Odometry,'/odom_combined',self.receive_odom,qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped,'/initialpose',self.initial_pose,10)
        self.match_group=MutuallyExclusiveCallbackGroup()
        self.create_timer(1.,self.tick,callback_group=self.match_group)

    def map(self,msg):
        self.matcher=LocalScanMatcher(np.asarray(msg.data).reshape(msg.info.height,msg.info.width),
            msg.info.resolution,(msg.info.origin.position.x,msg.info.origin.position.y,yaw(msg.info.origin.orientation)))
        self.good_once=False;self.bad_count=0

    def initial_pose(self,msg):
        stamp=(msg.header.stamp.sec,msg.header.stamp.nanosec)
        if stamp==self.own_stamp:return
        self.manual_ready=True;self.manual_at=time.monotonic();self.good_once=False;self.bad_count=0
        self.scans.clear();self.used=None
        self.get_logger().info('Manual initial pose received; bounded local refinement enabled')

    def receive_scan(self,msg):
        self.scan=msg;self.scan_at=time.monotonic()
        self.scans.append((msg,self.scan_at))

    def receive_odom(self,msg):
        self.odom=msg;self.odom_at=time.monotonic()

    def report(self,state,healthy=False,**values):
        self.status.publish(String(data=json.dumps(dict(state=state,healthy=healthy,**values))))

    def tick(self):
        if not self.manual_ready:
            self.report('set_2d_pose_estimate_first');return
        if time.monotonic()-self.manual_at<1.:
            self.report('waiting_for_manual_pose_to_settle');return
        if self.matcher is None or self.scan is None or time.monotonic()-self.scan_at>1.:
            self.report('map_or_scan_unavailable');return
        # Laser data can be 60-100 ms ahead of the 10 Hz EKF TF stream. Select
        # the newest buffered scan with a complete timestamped transform instead
        # of dropping every timer tick because the very newest scan is too new.
        selected=None;error='waiting for a synchronized scan'
        now=time.monotonic()
        manual_at=self.manual_at
        for candidate,received in reversed(list(self.scans)):
            if now-received>.5:break
            stamp=(candidate.header.stamp.sec,candidate.header.stamp.nanosec)
            if self.used is not None and stamp<=self.used:continue
            try:
                transform=self.tf.lookup_transform('map',candidate.header.frame_id,
                    rclpy.time.Time.from_msg(candidate.header.stamp))
                extrinsic=self.tf.lookup_transform('base_footprint',candidate.header.frame_id,rclpy.time.Time())
                selected=(candidate,stamp,received);break
            except Exception as exc:error=str(exc)
        if selected is None:
            self.report('timestamped_transform_unavailable',reason=error);return
        scan,stamp,received=selected;self.used=stamp
        ranges=np.asarray(scan.ranges)
        angles=scan.angle_min+np.arange(len(ranges))*scan.angle_increment
        valid=np.isfinite(ranges)&(ranges>max(.35,scan.range_min))&(ranges<min(5.,scan.range_max))
        points=np.column_stack((ranges[valid]*np.cos(angles[valid]),ranges[valid]*np.sin(angles[valid])))
        points=points[::max(1,int(math.ceil(len(points)/180)))]
        if len(points)<40:
            self.report('insufficient_scan_features');return
        pose=np.asarray([transform.transform.translation.x,transform.transform.translation.y,yaw(transform.transform.rotation)])
        result=self.matcher.match(points,pose)
        if self.manual_at!=manual_at:return  # Operator pose supersedes an in-flight match.
        quality_ok=alignment_supports_navigation(result)
        if quality_ok:
            self.good_once=True;self.bad_count=0
        else:
            self.bad_count+=1
        navigation_ok=quality_ok or (self.good_once and self.bad_count<3)
        values=dict(before_score=result['before_score'],after_score=result['after_score'],
            search_translation_m=self.matcher.translation,search_yaw_deg=math.degrees(self.matcher.rotation),
            synchronized_scan_delay_ms=round((now-received)*1000.,1),
            translation_error_m=float(np.linalg.norm(result['offset'][:2])),
            yaw_error_deg=float(math.degrees(result['offset'][2])))
        if result['apply']:
            corrected=pose+result['correction']
            ex=extrinsic.transform.translation;heading=corrected[2]-yaw(extrinsic.transform.rotation)
            c,s=math.cos(heading),math.sin(heading)
            base=[corrected[0]-c*ex.x+s*ex.y,corrected[1]-s*ex.x-c*ex.y,heading]
            try:
                old=self.tf.lookup_transform(self.odom_frame,'base_footprint',rclpy.time.Time.from_msg(scan.header.stamp))
                latest=self.tf.lookup_transform(self.odom_frame,'base_footprint',rclpy.time.Time())
                published=self.get_clock().now()
                age=(published-rclpy.time.Time.from_msg(latest.header.stamp)).nanoseconds/1e9
                odom_age=(published-rclpy.time.Time.from_msg(self.odom.header.stamp)).nanoseconds/1e9 if self.odom else math.inf
                if not (0.<=age<=.20 and 0.<=odom_age<=.25 and time.monotonic()-self.odom_at<.25):
                    # An unavailable NEW correction is not a failed existing
                    # scan/map match. Sensor watchdogs still enforce freshness.
                    self.report('motion_compensation_unavailable',navigation_ok,tf_age_s=age,odom_age_s=odom_age,**values);return
                def planar(t):
                    return [t.transform.translation.x,t.transform.translation.y,yaw(t.transform.rotation)]
                twist=self.odom.twist.twist
                base=propagate_pose(base,planar(old),planar(latest),
                    [twist.linear.x,twist.linear.y,twist.angular.z],age)
            except Exception as exc:
                self.report('motion_compensation_unavailable',navigation_ok,reason=str(exc),**values);return
            msg=PoseWithCovarianceStamped();msg.header.frame_id='map'
            # Already compensated to now; AMCL's often unavailable future TF
            # lookup must not discard the scan-to-now rotation a second time.
            msg.header.stamp=published.to_msg()
            msg.pose.pose.position.x=float(base[0]);msg.pose.pose.position.y=float(base[1]);heading=base[2]
            msg.pose.pose.orientation.z=math.sin(heading/2);msg.pose.pose.orientation.w=math.cos(heading/2)
            msg.pose.covariance[0]=msg.pose.covariance[7]=.03**2
            msg.pose.covariance[35]=math.radians(1.)**2
            self.own_stamp=(msg.header.stamp.sec,msg.header.stamp.nanosec);self.pose_pub.publish(msg)
            values.update(motion_compensation_s=age,applied_yaw_deg=math.degrees(result['correction'][2]))
            self.report('locally_corrected',navigation_ok,**values)
            self.get_logger().info('Local correction: %.3f m, %.3f deg' %
                (np.linalg.norm(result['correction'][:2]),math.degrees(result['correction'][2])))
        elif quality_ok:
            self.report('tracking_correction_limited' if result['boundary'] else 'tracking',True,**values)
        else:
            self.report('outside_local_range_or_poor_match',navigation_ok,**values)


def main(args=None):
    # A manually restarted orphan and a launch-owned node must never publish
    # competing corrections on /initialpose. Separate test domains stay isolated.
    lock_path=Path('/tmp')/('ic382-local-alignment-%s-%s.lock' %
        (os.getuid(),os.environ.get('ROS_DOMAIN_ID','0')))
    instance_lock=lock_path.open('a')
    try:fcntl.flock(instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        instance_lock.close()
        raise RuntimeError('local_alignment already running in this ROS domain; duplicate refused')
    rclpy.init(args=args);node=LocalAlignment()
    executor=MultiThreadedExecutor(num_threads=2);executor.add_node(node)
    try:executor.spin()
    except (KeyboardInterrupt,ExternalShutdownException):pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
        instance_lock.close()
