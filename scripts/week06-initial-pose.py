import rclpy,time,json,math
from rclpy.parameter import Parameter
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.qos import qos_profile_sensor_data
rclpy.init();n=rclpy.create_node('ic382_set_initial_pose',parameter_overrides=[Parameter('use_sim_time',value=True)]);last={}
s=n.create_subscription(Odometry,'odom',lambda m:last.update(odom=m),qos_profile_sensor_data);p=n.create_publisher(PoseWithCovarianceStamped,'initialpose',10)
end=time.time()+30
while 'odom' not in last and time.time()<end:rclpy.spin_once(n,timeout_sec=.1)
if 'odom' not in last:raise RuntimeError('No simulation odometry available')
d=json.load(open('/workspace/dev/map/map_to_odom.json'));a=last['odom'].pose.pose;q=a.orientation;yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));q=d['rotation'];offset=math.atan2(2*(q[3]*q[2]+q[0]*q[1]),1-2*(q[1]*q[1]+q[2]*q[2]));x=a.position.x-1.189*math.cos(yaw);y=a.position.y-1.189*math.sin(yaw)
m=PoseWithCovarianceStamped();m.header.frame_id='map';m.pose.pose.position.x=d['translation'][0]+math.cos(offset)*x-math.sin(offset)*y;m.pose.pose.position.y=d['translation'][1]+math.sin(offset)*x+math.cos(offset)*y;m.pose.pose.orientation.z=math.sin((yaw+offset)/2);m.pose.pose.orientation.w=math.cos((yaw+offset)/2);m.pose.covariance[0]=.25;m.pose.covariance[7]=.25;m.pose.covariance[35]=.04
for _ in range(5):
 m.header.stamp=n.get_clock().now().to_msg();p.publish(m);end=time.time()+1
 while time.time()<end:rclpy.spin_once(n,timeout_sec=.1)
print('IC382_INITIAL_POSE_SET',m.pose.pose,flush=True);n.destroy_node();rclpy.shutdown()
