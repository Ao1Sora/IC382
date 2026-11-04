import rclpy,time,json,math
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseWithCovarianceStamped,Twist
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer,TransformListener
rclpy.init();n=Node('ic382_navigation_verification',parameter_overrides=[Parameter('use_sim_time',value=True)])
pub=n.create_publisher(PoseWithCovarianceStamped,'initialpose',10);stop=n.create_publisher(Twist,'cmd_vel',10);last={}
s=n.create_subscription(PoseWithCovarianceStamped,'amcl_pose',lambda m:last.update(pose=m),10)
b=Buffer();t=TransformListener(b,n);client=ActionClient(n,NavigateToPose,'navigate_to_pose')
def spin(sec):
 end=time.time()+sec
 while time.time()<end:rclpy.spin_once(n,timeout_sec=.1)
data=json.load(open('/workspace/logs/week06-mapped-pose.json'))
initial=PoseWithCovarianceStamped();initial.header.frame_id='map';p=initial.pose.pose.position;q=initial.pose.pose.orientation
p.x,p.y=data['position'][:2];q.x,q.y,q.z,q.w=data['orientation'];initial.pose.covariance[0]=.04;initial.pose.covariance[7]=.04;initial.pose.covariance[35]=.01
spin(3)
for _ in range(3):initial.header.stamp=n.get_clock().now().to_msg();pub.publish(initial);spin(2)
deadline=time.time()+40
while 'pose' not in last and time.time()<deadline:spin(.2)
if 'pose' not in last:raise RuntimeError('AMCL did not localize after initial pose')
ap=last['pose'].pose.pose;print('AMCL_LOCALIZED',ap,flush=True)
if not client.wait_for_server(timeout_sec=40):raise RuntimeError('NavigateToPose action unavailable')
q=ap.orientation;yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
goal=NavigateToPose.Goal();goal.pose.header.frame_id='map';goal.pose.header.stamp=n.get_clock().now().to_msg();goal.pose.pose.position.x=ap.position.x+2.5*math.cos(yaw);goal.pose.pose.position.y=ap.position.y+2.5*math.sin(yaw);goal.pose.pose.orientation=q
result={'start':[ap.position.x,ap.position.y],'goal':[goal.pose.pose.position.x,goal.pose.pose.position.y],'initial_pose':data,'feedback':[]};lastprint=0
def feedback(msg):
 global lastprint
 if time.time()-lastprint>5:
  f=msg.feedback;entry={'distance_remaining':f.distance_remaining,'recoveries':f.number_of_recoveries};result['feedback'].append(entry);print('NAV_FEEDBACK',entry,flush=True);lastprint=time.time()
future=client.send_goal_async(goal,feedback_callback=feedback);rclpy.spin_until_future_complete(n,future,timeout_sec=15);handle=future.result()
if handle is None or not handle.accepted:raise RuntimeError('Navigation goal was rejected')
print('NAV_GOAL_ACCEPTED',result['goal'],flush=True);f=handle.get_result_async();rclpy.spin_until_future_complete(n,f,timeout_sec=150)
if not f.done():
 handle.cancel_goal_async();spin(3);result['status']='timeout'
else:result['status']=f.result().status
stop.publish(Twist());spin(1)
try:
 tf=b.lookup_transform('map','base_footprint',rclpy.time.Time());p=tf.transform.translation;result['final']=[p.x,p.y];result['final_error']=math.hypot(p.x-result['goal'][0],p.y-result['goal'][1]);result['actual_displacement']=math.hypot(p.x-result['start'][0],p.y-result['start'][1])
except Exception as e:result['tf_error']=str(e)
open('/workspace/logs/week06-navigation-result.json','w').write(json.dumps(result,indent=2));print('NAV_RESULT',json.dumps(result),flush=True)
if result['status']==4:print('IC382_WEEK06_NAVIGATION_PASSED',flush=True)
else:print('IC382_WEEK06_NAVIGATION_NOT_PASSED',flush=True)
n.destroy_node();rclpy.shutdown()
