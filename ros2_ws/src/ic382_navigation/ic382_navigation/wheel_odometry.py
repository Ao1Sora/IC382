"""Encoder-only differential-drive odometry; no IMU, AMCL or simulator pose input."""
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
from .inspection import WheelIntegrator


class WheelOdometry(Node):
    def __init__(self):
        super().__init__('wheel_odometry')
        # Effective constants fitted OFFLINE for the repaired scene contacts.
        radius = float(self.declare_parameter('wheel_radius', .630835).value)
        track = float(self.declare_parameter('wheel_track', 3.611644).value)
        turn_track = float(self.declare_parameter('turn_track', 3.611644).value)
        blend = float(self.declare_parameter('turn_blend_speed', .5).value)
        self.model = WheelIntegrator(radius, track, turn_track=turn_track, turn_blend_speed=blend)
        self.height = float(self.declare_parameter('base_height', .63).value)
        if not math.isfinite(self.height) or self.height<=0:
            raise ValueError('Base height must be positive')
        self.fault = False
        self.mode = None
        self.publisher = self.create_publisher(Odometry, 'odom', 20)
        self.tf = TransformBroadcaster(self)
        self.create_subscription(JointState, 'joint_states', self.sample, qos_profile_sensor_data)

    def sample(self, msg):
        if self.fault:
            return
        try:
            indices = [msg.name.index(n) for n in ('left_wheel_joint', 'right_wheel_joint')]
            mode = 'position' if msg.position else 'velocity'
            if self.mode is not None and mode != self.mode:
                raise ValueError('Encoder input mode changed; reinitialize localization')
            self.mode = mode
            values = msg.position if mode == 'position' else msg.velocity
            left, right = [values[i] for i in indices]
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
            if self.model.previous is not None and stamp == self.model.previous[0]:
                return  # A paused simulator must not publish fresh-looking odometry.
            update = self.model.update_positions if mode == 'position' else self.model.update
            x, y, yaw, v, w = update(stamp, left, right)
        except (ValueError, IndexError) as exc:
            self.fault = True
            self.get_logger().error(str(exc))
            # No more odometry/TF: the independent navigation watchdog stops motion.
            return
        odom = Odometry()
        odom.header.stamp = msg.header.stamp
        odom.header.frame_id = 'odom'; odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = x; odom.pose.pose.position.y = y
        odom.pose.pose.position.z = self.height
        odom.pose.pose.orientation.z = math.sin(yaw / 2)
        odom.pose.pose.orientation.w = math.cos(yaw / 2)
        odom.twist.twist.linear.x = v; odom.twist.twist.angular.z = w
        variance = .001 + .01 * math.hypot(x, y)
        odom.pose.covariance[0] = odom.pose.covariance[7] = variance
        odom.pose.covariance[35] = variance * .1
        self.publisher.publish(odom)
        transform = TransformStamped()
        transform.header = odom.header; transform.child_frame_id = odom.child_frame_id
        transform.transform.translation.x = x; transform.transform.translation.y = y
        transform.transform.translation.z = self.height
        transform.transform.rotation = odom.pose.pose.orientation
        self.tf.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)
    node = WheelOdometry()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
