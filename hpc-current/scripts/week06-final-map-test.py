import rclpy,time,math,json
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid,Odometry
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer,TransformListener
rclpy.init(); n=Node('ic382_course_explore'); pub=n.create_publisher(Twist,'cmd_vel',10); last={}
subs=[n.create_subscription(c,t,lambda m,k=t:last.update({k:m}),10) for c,t in [(OccupancyGrid,'map'),(Odometry,'odom'),(LaserScan,'scan_corrected')]]
b=Buffer(); listener=TransformListener(b,n)
def spin(sec,v=0,w=0):
 end=time.time()+sec
 while time.time()<end:
  cmd=Twist();cmd.linear.x=float(v);cmd.angular.z=float(w);pub.publish(cmd);rclpy.spin_once(n,timeout_sec=.05)
spin(4)
o=last.get('odom');print('START_ODOM',o.pose.pose if o else None,flush=True)
scan=last.get('scan')
if scan:
 for label,a in [('front',0),('left',math.pi/2),('rear',math.pi),('right',-math.pi/2)]:
  vals=[r for i,r in enumerate(scan.ranges) if abs(math.atan2(math.sin(scan.angle_min+i*scan.angle_increment-a),math.cos(scan.angle_min+i*scan.angle_increment-a)))<.2 and math.isfinite(r)]; print('CLEARANCE',label,min(vals) if vals else None,flush=True)
spin(12,.3,0);spin(2);spin(10,-.3,0);spin(5)
o=last.get('odom');print('END_ODOM',o.pose.pose if o else None,flush=True)
m=last.get('map')
if m: print('MAP',m.info.width,m.info.height,m.info.resolution,'KNOWN',sum(x>=0 for x in m.data),'OCCUPIED',sum(x>50 for x in m.data),flush=True)
try:
 t=b.lookup_transform('map','base_footprint',rclpy.time.Time());p=t.transform.translation;q=t.transform.rotation
 result={'position':[p.x,p.y,p.z],'orientation':[q.x,q.y,q.z,q.w]};open('/workspace/logs/week06-mapped-pose.json','w').write(json.dumps(result));print('MAPPED_POSE',result,flush=True)
except Exception as e: print('TF_ERROR',str(e),flush=True)
n.destroy_node();rclpy.shutdown()
