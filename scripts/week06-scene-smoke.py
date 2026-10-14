import os,time,json,traceback
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'width':640,'height':360,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from isaacsim.core.utils.extensions import enable_extension
    for extension in ['isaacsim.ros2.bridge','isaacsim.robot.wheeled_robots','isaacsim.sensors.rtx','isaacsim.sensors.physx']:
        enable_extension(extension)
    import omni.usd,omni.timeline,omni.graph.core as og
    from pxr import UsdGeom,UsdPhysics
    context=omni.usd.get_context()
    context.open_stage('/workspace/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd')
    for _ in range(20): app.update()
    stage=context.get_stage()
    graph='/World/senior_diff_robot_scaled/senior_diff_robot/Graph/ROS_Master_graph_nav2'
    print('COURSE_STAGE_LOADED',flush=True)
    for p in stage.Traverse():
        if p.GetAttribute('node:type').IsValid():
            ntype=p.GetAttribute('node:type').Get()
            print('GRAPH_NODE',str(p.GetPath()),ntype,'RUNTIME_VERSION',og.get_node_type_version(ntype),flush=True)
        if p.GetName()=='Lidar':
            print('LIDAR_SCHEMA',str(p.GetPath()),p.GetTypeName(),[(a.GetName(),str(a.Get())) for a in p.GetAttributes()],flush=True)
    import rclpy
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from geometry_msgs.msg import Twist
    from rclpy.qos import qos_profile_sensor_data
    rclpy.init(); node=rclpy.create_node('ic382_course_probe')
    counts={'clock':0,'scan':0,'odom':0}; last={}
    def received(key,msg):
        counts[key]+=1; last[key]=msg
    subscriptions=[node.create_subscription(typ,'/'+key,lambda m,k=key:received(k,m),qos_profile_sensor_data) for key,typ in [('clock',Clock),('scan',LaserScan),('odom',Odometry)]]
    publisher=node.create_publisher(Twist,'/cmd_vel',10)
    omni.timeline.get_timeline_interface().play()
    start=time.time()
    for i in range(240):
        app.update(); rclpy.spin_once(node,timeout_sec=0.0)
        if i%30==0: print('COURSE_SENSOR_COUNTS',counts,flush=True)
        if time.time()-start>120: break
    print('COURSE_FINAL_COUNTS',counts,flush=True)
    if all(counts.values()): print('IC382_WEEK06_SCENE_SMOKE_PASSED',flush=True)
    else: print('IC382_WEEK06_SCENE_SMOKE_INCOMPLETE',flush=True)
    omni.timeline.get_timeline_interface().stop()
    node.destroy_node(); rclpy.shutdown()
except Exception:
    traceback.print_exc(); print('IC382_WEEK06_SCENE_SMOKE_FAILED',flush=True)
finally: app.close()
