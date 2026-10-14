import rclpy,math
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
rclpy.init();n=rclpy.create_node('ic382_isaac45_scan_adapter');p=n.create_publisher(LaserScan,'scan_corrected',10);last=None
def cb(m):
 global last
 key=(m.header.stamp.sec,m.header.stamp.nanosec)
 if key==last:return
 last=key
 limit=m.range_max
 # Isaac RTX uses -1 for rays with no return within the sensor range.
 # Karto ignores inf and values >= range_max; represent no-return rays
 # between its raster threshold (30.0m) and declared max (30.1m),
 # so it traces free space without marking a false obstacle endpoint.
 m.ranges=[limit if v==-1.0 else v for v in m.ranges];m.range_max=limit+.1;p.publish(m)
s=n.create_subscription(LaserScan,'scan',cb,qos_profile_sensor_data)
print('IC382_SCAN_ADAPTER_RUNNING',flush=True)
rclpy.spin(n)
