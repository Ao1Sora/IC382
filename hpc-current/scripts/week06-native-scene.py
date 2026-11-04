import os,time,traceback,json
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'width':640,'height':360,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from isaacsim.core.utils.extensions import enable_extension
    for name in ['isaacsim.ros2.bridge','isaacsim.robot.wheeled_robots','isaacsim.sensors.rtx']: enable_extension(name)
    from pxr import Usd,Sdf
    from pathlib import Path
    folder=Path('/workspace/dev/Collected_final_wheeltec_with_scene')
    overlay=folder/'final_wheeltec_hpc45_native.usda'
    root='/World/senior_diff_robot_scaled/senior_diff_robot'
    base=root+'/senior_diff_robot/Geometry/base_link'
    if not overlay.exists():
        stage=Usd.Stage.CreateNew(str(overlay)); stage.GetRootLayer().subLayerPaths=['final_wheeltec_hpc45_flat.usdc']
        stage.OverridePrim(root+'/Graph').SetActive(False)
        stage.OverridePrim('/Render').SetActive(True)
        stage.SetDefaultPrim(stage.GetPrimAtPath('/World')); stage.GetRootLayer().Save()
    stage=Usd.Stage.Open(str(overlay)); stage.OverridePrim('/Render').SetActive(True); stage.GetRootLayer().Save()
    import omni.usd,omni.timeline,omni.graph.core as og
    context=omni.usd.get_context(); context.open_stage(str(overlay))
    for _ in range(20): app.update()
    print('COURSE_NATIVE_STAGE_LOADED',flush=True)
    keys=og.Controller.Keys
    nodes=[('Tick','omni.graph.action.OnPlaybackTick'),('Context','isaacsim.ros2.bridge.ROS2Context'),('Time','isaacsim.core.nodes.IsaacReadSimulationTime'),('Clock','isaacsim.ros2.bridge.ROS2PublishClock'),('Twist','isaacsim.ros2.bridge.ROS2SubscribeTwist'),('Linear','omni.graph.nodes.BreakVector3'),('Angular','omni.graph.nodes.BreakVector3'),('Drive','isaacsim.robot.wheeled_robots.DifferentialController'),('Articulation','isaacsim.core.nodes.IsaacArticulationController'),('Odom','isaacsim.core.nodes.IsaacComputeOdometry'),('OdomPub','isaacsim.ros2.bridge.ROS2PublishOdometry'),('OdomTF','isaacsim.ros2.bridge.ROS2PublishRawTransformTree'),('SensorTF','isaacsim.ros2.bridge.ROS2PublishTransformTree'),('LidarProduct','isaacsim.core.nodes.IsaacCreateRenderProduct'),('LidarPub','isaacsim.ros2.bridge.ROS2RtxLidarHelper')]
    edges=[]
    for node in ['Clock','Twist','Drive','Articulation','Odom','SensorTF','LidarProduct']:
        edges.append(('Tick.outputs:tick',node+'.inputs:execIn'))
    for node in ['Clock','Twist','OdomPub','OdomTF','SensorTF','LidarPub']:
        edges.append(('Context.outputs:context',node+'.inputs:context'))
    edges += [('Time.outputs:simulationTime','Clock.inputs:timeStamp'),('Twist.outputs:linearVelocity','Linear.inputs:tuple'),('Twist.outputs:angularVelocity','Angular.inputs:tuple'),('Linear.outputs:x','Drive.inputs:linearVelocity'),('Angular.outputs:z','Drive.inputs:angularVelocity'),('Drive.outputs:velocityCommand','Articulation.inputs:velocityCommand'),('Odom.outputs:execOut','OdomPub.inputs:execIn'),('Odom.outputs:execOut','OdomTF.inputs:execIn'),('Odom.outputs:position','OdomPub.inputs:position'),('Odom.outputs:orientation','OdomPub.inputs:orientation'),('Odom.outputs:linearVelocity','OdomPub.inputs:linearVelocity'),('Odom.outputs:angularVelocity','OdomPub.inputs:angularVelocity'),('Odom.outputs:position','OdomTF.inputs:translation'),('Odom.outputs:orientation','OdomTF.inputs:rotation'),('Time.outputs:simulationTime','OdomPub.inputs:timeStamp'),('Time.outputs:simulationTime','OdomTF.inputs:timeStamp'),('Time.outputs:simulationTime','SensorTF.inputs:timeStamp'),('LidarProduct.outputs:execOut','LidarPub.inputs:execIn'),('LidarProduct.outputs:renderProductPath','LidarPub.inputs:renderProductPath')]
    values=[('Context.inputs:domain_id',82),('Twist.inputs:topicName','cmd_vel'),('Drive.inputs:wheelRadius',0.63),('Drive.inputs:wheelDistance',3.627),('Articulation.inputs:jointNames',['left_wheel_joint','right_wheel_joint']),('Articulation.inputs:targetPrim',[Sdf.Path(base)]),('Odom.inputs:chassisPrim',[Sdf.Path(base)]),('OdomPub.inputs:topicName','odom'),('OdomPub.inputs:odomFrameId','odom'),('OdomPub.inputs:chassisFrameId','base_link'),('OdomTF.inputs:parentFrameId','odom'),('OdomTF.inputs:childFrameId','base_link'),('SensorTF.inputs:parentPrim',[Sdf.Path(base)]),('SensorTF.inputs:targetPrims',[Sdf.Path(base+'/'+n) for n in ['laser_link','camera_link','left_wheel_link','right_wheel_link','quanxiang_wheel_link','controller_link']]),('LidarProduct.inputs:cameraPrim',[Sdf.Path(base+'/laser_link/Lidar')]),('LidarProduct.inputs:width',128),('LidarProduct.inputs:height',1),('LidarPub.inputs:topicName','scan'),('LidarPub.inputs:frameId','laser_link'),('LidarPub.inputs:type','laser_scan')]
    og.Controller.edit({'graph_path':'/World/IC382_ROS2','evaluator_name':'execution'},{keys.CREATE_NODES:nodes,keys.CONNECT:edges,keys.SET_VALUES:values})
    print('COURSE_NATIVE_GRAPH_CREATED',flush=True)
    import rclpy
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from rclpy.qos import qos_profile_sensor_data
    rclpy.init(); node=rclpy.create_node('ic382_native_probe')
    counts={'clock':0,'scan':0,'odom':0}
    def received(key,msg): counts[key]+=1
    subscriptions=[node.create_subscription(typ,'/'+key,lambda m,k=key:received(k,m),qos_profile_sensor_data) for key,typ in [('clock',Clock),('scan',LaserScan),('odom',Odometry)]]
    omni.timeline.get_timeline_interface().play()
    start=time.time()
    for i in range(300):
        app.update(); rclpy.spin_once(node,timeout_sec=0.0)
        if i%30==0: print('COURSE_NATIVE_SENSOR_COUNTS',counts,flush=True)
        if time.time()-start>120: break
    print('COURSE_NATIVE_FINAL_COUNTS',counts,flush=True)
    if all(counts.values()): print('IC382_WEEK06_NATIVE_SCENE_PASSED',flush=True)
    else: print('IC382_WEEK06_NATIVE_SCENE_INCOMPLETE',flush=True)
    omni.timeline.get_timeline_interface().stop(); node.destroy_node(); rclpy.shutdown()
except Exception:
    traceback.print_exc(); print('IC382_WEEK06_NATIVE_SCENE_FAILED',flush=True)
finally: app.close()
