"""Short commanded-motion and ROS2 bridge check for the CAD robot in simulation."""
import json,math,time
from pathlib import Path
import rclpy
from geometry_msgs.msg import Twist
from lifecycle_msgs.srv import ChangeState,GetState

path=Path('/workspace/logs/course601-live.json')
def state():
    return json.loads(path.read_text())

rclpy.init()
node=rclpy.create_node('ic382_team_robot_acceptance')
publisher=node.create_publisher(Twist,'/cmd_vel',10)
trace=[]
def lifecycle(service,request):
    client=node.create_client(GetState if isinstance(request,GetState.Request) else ChangeState,service)
    if not client.wait_for_service(timeout_sec=3):return None
    future=client.call_async(request)
    rclpy.spin_until_future_complete(node,future,timeout_sec=3)
    return future.result() if future.done() else None
old_state=lifecycle('/velocity_smoother/get_state',GetState.Request())
paused=old_state is not None and old_state.current_state.id==3
if paused:
    request=ChangeState.Request();request.transition.id=4
    response=lifecycle('/velocity_smoother/change_state',request)
    if response is None or not response.success:raise RuntimeError('Could not pause velocity smoother for exclusive manual test')
def phase(seconds,v=0.,w=0.):
    message=Twist();message.linear.x=v;message.angular.z=w
    end=time.monotonic()+seconds
    next_sample=0
    while time.monotonic()<end:
        publisher.publish(message)
        rclpy.spin_once(node,timeout_sec=.05)
        if (v or w) and time.monotonic()>next_sample:
            s=state();trace.append({k:s.get(k) for k in ['received_cmd','applied_wheels','joint_velocities','world_pose']})
            next_sample=time.monotonic()+1

def yaw(s):
    w,x,y,z=s['world_orientation']
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))

try:
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        s=state()
        if time.time()-path.stat().st_mtime<3 and s.get('robot_source')=='team_robot_20261013' and s.get('sim_time',0)>3 and s.get('counts',{}).get('scan',0)>8:
            break
        phase(1)
    before=state()
    if before.get('robot_source')!='team_robot_20261013':raise RuntimeError('Wrong active robot')
    if not before.get('scan'):raise RuntimeError('No lidar data; motion test refused')
    phase(7,v=.3)
    phase(2)
    straight=state()
    phase(7,w=.15)
    phase(2)
    after=state()
    xy=math.dist(before['world_pose'][:2],straight['world_pose'][:2])
    angle=math.atan2(math.sin(yaw(after)-yaw(straight)),math.cos(yaw(after)-yaw(straight)))
    scan=after.get('scan',{})
    ranges=scan.get('ranges',[])
    valid=sum(v is not None and math.isfinite(v) and scan['range_min']<=v<=scan['range_max'] and v>0 for v in ranges)
    stable=abs(after['world_pose'][2]-before['world_pose'][2])<.3
    counts_advanced=all(after['counts'][k]>before['counts'][k] for k in ['clock','scan','odom'])
    result=dict(robot_source=after.get('robot_source'),straight_distance_scene_units=xy,
                yaw_change_radians=angle,stable_height=stable,counts_advanced=counts_advanced,
                counts_before=before['counts'],counts_after=after['counts'],valid_lidar_returns=valid,
                lidar_rays=len(ranges),scene_scale=after['robot_setup']['scene_scale'],
                before_pose=before['world_pose'],after_pose=after['world_pose'],trace=trace,
                passed=xy>.03 and abs(angle)>.015 and stable and counts_advanced and valid>0)
    Path('/workspace/logs/team-robot-acceptance.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
finally:
    phase(1)
    if paused:
        request=ChangeState.Request();request.transition.id=3
        lifecycle('/velocity_smoother/change_state',request)
    node.destroy_node();rclpy.shutdown()
