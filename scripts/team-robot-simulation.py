import os,time,traceback,json
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'hide_ui':False,'limit_cpu_threads':6,'width':1920,'height':1080,'window_width':1920,'window_height':1080,'extra_args':['--/rtx/verifyDriverVersion/enabled=false','--/exts/omni.kit.livestream.app/primaryStream/publicIp=10.238.38.1','--/exts/omni.kit.livestream.app/primaryStream/allowDynamicResize=false','--/app/livestream/allowResize=false','--/app/extensions/registryEnabled=false','--/persistent/isaac/asset_root/default=/workspace/dev','--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']},experience='/workspace/tools/isaacsim-6.0.1/apps/isaacsim.exp.full.streaming.kit')
try:
    from isaacsim.core.utils.extensions import enable_extension
    app.set_setting('/app/window/drawMouse',True)
    app.set_setting('/rtx/post/tonemap/op',6)
    app.set_setting('/rtx/post/tonemap/filmIso',50.)
    app.set_setting('/rtx/post/tonemap/fNumber',8.)
    app.set_setting('/rtx/post/tonemap/exposureTime',.01)
    enable_extension('omni.kit.livestream.app')
    print('IC382_COURSE601_STREAM_EXTENSION_ENABLED',flush=True)
    for name in ['isaacsim.ros2.bridge','isaacsim.robot.wheeled_robots','isaacsim.sensors.rtx']: enable_extension(name)
    from pxr import Usd,Sdf
    from pathlib import Path
    folder=Path('/workspace/dev/Collected_final_wheeltec_with_scene')
    overlay=folder/'final_wheeltec_hpc45_native.usda'
    root='/World/senior_diff_robot_scaled/senior_diff_robot'
    base=root+'/senior_diff_robot/Geometry/base_link'
    overlay=folder/'final_wheeltec_hpc45_clean.usdc'
    import runpy
    overlay=runpy.run_path('/workspace/scripts/repair-course-scene.py')['repair_scene'](overlay,Path('/workspace/cache/course-scene-repaired.usda'),folder)
    import omni.usd,omni.timeline,omni.graph.core as og
    context=omni.usd.get_context()
    from isaacsim.core.api import World
    world=World(stage_units_in_meters=1.0)
    stage=context.get_stage()
    stage.DefinePrim('/World','Xform').GetReferences().AddReference(str(overlay),'/World')
    for _ in range(20): app.update()
    print('COURSE_NATIVE_STAGE_LOADED',flush=True)
    from pxr import UsdPhysics
    from pxr import Gf,UsdGeom
    import omni.kit.commands
    import runpy
    original_base=base
    setup=runpy.run_path('/workspace/scripts/team-robot-loader.py')['install_team_robot'](stage,root,base)
    root=setup['root'];base=setup['base']
    setup['contacts']=runpy.run_path('/workspace/scripts/robot-contact-profile.py')['configure_contacts'](stage,root)
    wheel_radius=setup['wheel_radius'];wheel_track=setup['wheel_track']
    # Coordinates and inertias are baked at scene_scale; preserve real-world
    # free-fall acceleration while keeping the existing map/ROS coordinates.
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.Scene):
            UsdPhysics.Scene(prim).CreateGravityMagnitudeAttr(9.81*setup['scene_scale'])
    sensor_layer=Sdf.Layer.FindOrOpen('/workspace/dev/Collected_final_wheeltec_with_scene/course-original-lidar.usda')
    Sdf.CreatePrimInLayer(stage.GetRootLayer(),base+'/laser_link/Lidar')
    Sdf.CopySpec(sensor_layer,original_base+'/laser_link/Lidar',stage.GetRootLayer(),base+'/laser_link/Lidar')
    stage.GetPrimAtPath(base+'/laser_link/Lidar').SetActive(True)
    print('COURSE_ORIGINAL_OMNILIDAR_RESTORED',flush=True)
    print('COURSE601_JOINTS_READY',flush=True)
    keys=og.Controller.Keys
    nodes=[('Tick','omni.graph.action.OnPlaybackTick'),('Context','isaacsim.ros2.bridge.ROS2Context'),('Time','isaacsim.core.nodes.IsaacReadSimulationTime'),('Clock','isaacsim.ros2.bridge.ROS2PublishClock'),('Twist','isaacsim.ros2.bridge.ROS2SubscribeTwist'),('Linear','omni.graph.nodes.BreakVector3'),('Angular','omni.graph.nodes.BreakVector3'),('Drive','isaacsim.robot.wheeled_robots.DifferentialController'),('Articulation','isaacsim.core.nodes.IsaacArticulationController'),('Odom','isaacsim.core.nodes.IsaacComputeOdometry'),('OdomPub','isaacsim.ros2.bridge.ROS2PublishOdometry'),('OdomTF','isaacsim.ros2.bridge.ROS2PublishRawTransformTree'),('SensorTF','isaacsim.ros2.bridge.ROS2PublishTransformTree'),('LidarProduct','isaacsim.core.nodes.IsaacCreateRenderProduct'),('LidarPub','isaacsim.ros2.bridge.ROS2RtxLidarHelper')]
    edges=[]
    for node in ['Clock','Twist','Odom','SensorTF','LidarProduct']:
        edges.append(('Tick.outputs:tick',node+'.inputs:execIn'))
    for node in ['Clock','Twist','OdomPub','OdomTF','SensorTF','LidarPub']:
        edges.append(('Context.outputs:context',node+'.inputs:context'))
    edges += [('Twist.outputs:execOut','Drive.inputs:execIn'),('Time.outputs:simulationTime','Clock.inputs:timeStamp'),('Twist.outputs:linearVelocity','Linear.inputs:tuple'),('Twist.outputs:angularVelocity','Angular.inputs:tuple'),('Linear.outputs:x','Drive.inputs:linearVelocity'),('Angular.outputs:z','Drive.inputs:angularVelocity'),('Drive.outputs:velocityCommand','Articulation.inputs:velocityCommand'),('Odom.outputs:execOut','OdomPub.inputs:execIn'),('Odom.outputs:execOut','OdomTF.inputs:execIn'),('Odom.outputs:position','OdomPub.inputs:position'),('Odom.outputs:orientation','OdomPub.inputs:orientation'),('Odom.outputs:linearVelocity','OdomPub.inputs:linearVelocity'),('Odom.outputs:angularVelocity','OdomPub.inputs:angularVelocity'),('Odom.outputs:position','OdomTF.inputs:translation'),('Odom.outputs:orientation','OdomTF.inputs:rotation'),('Time.outputs:simulationTime','OdomPub.inputs:timeStamp'),('Time.outputs:simulationTime','OdomTF.inputs:timeStamp'),('Time.outputs:simulationTime','SensorTF.inputs:timeStamp'),('LidarProduct.outputs:execOut','LidarPub.inputs:execIn'),('LidarProduct.outputs:renderProductPath','LidarPub.inputs:renderProductPath')]
    values=[('Context.inputs:domain_id',82),('Twist.inputs:topicName','cmd_vel'),('Drive.inputs:wheelRadius',wheel_radius),('Drive.inputs:wheelDistance',wheel_track),('Articulation.inputs:jointNames',['left_wheel_joint','right_wheel_joint']),('Articulation.inputs:targetPrim',[Sdf.Path(root)]),('Odom.inputs:chassisPrim',[Sdf.Path(base)]),('OdomPub.inputs:topicName','odom'),('OdomPub.inputs:odomFrameId','odom'),('OdomPub.inputs:chassisFrameId','base_link'),('OdomTF.inputs:parentFrameId','odom'),('OdomTF.inputs:childFrameId','base_link'),('SensorTF.inputs:parentPrim',[Sdf.Path(base)]),('SensorTF.inputs:targetPrims',[Sdf.Path(p) for p in setup['sensor_frames'] if p.endswith('_wheel_link')]),('LidarProduct.inputs:cameraPrim',[Sdf.Path(base+'/laser_link/Lidar')]),('LidarProduct.inputs:width',128),('LidarProduct.inputs:height',1),('LidarPub.inputs:topicName','scan'),('LidarPub.inputs:frameId','laser_link'),('LidarPub.inputs:type','laser_scan')]
    nodes=[n for n in nodes if n[0] not in ['Articulation','SensorTF']]
    # Simulator truth is diagnostic only. Navigation consumes measured wheel
    # velocities and supplies its own odom -> base_link transform.
    diagnostic_values={'OdomPub.inputs:topicName':'sim/ground_truth_odom',
                       'OdomPub.inputs:odomFrameId':'sim_ground_truth',
                       'OdomPub.inputs:chassisFrameId':'sim_base_link',
                       'OdomTF.inputs:parentFrameId':'sim_ground_truth',
                       'OdomTF.inputs:childFrameId':'sim_base_link'}
    values=[(key,diagnostic_values.get(key,value)) for key,value in values]
    edges=[e for e in edges if not any(v.startswith(('Articulation.','SensorTF.')) for v in e)]
    values=[v for v in values if not v[0].startswith(('Articulation.','SensorTF.'))]
    og.Controller.edit({'graph_path':'/World/IC382_ROS2','evaluator_name':'execution'},{keys.CREATE_NODES:nodes,keys.CONNECT:edges,keys.SET_VALUES:values})
    print('COURSE_NATIVE_GRAPH_CREATED',flush=True)
    import rclpy
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.context import Context
    probe_context=Context();rclpy.init(context=probe_context);node=rclpy.create_node('ic382_team_probe',context=probe_context)
    from rclpy.executors import SingleThreadedExecutor
    team_executor=SingleThreadedExecutor(context=probe_context);team_executor.add_node(node)
    counts={'clock':0,'scan':0,'odom':0}
    last={}
    def received(key,msg): counts[key]+=1; last[key]=msg
    subscriptions=[node.create_subscription(typ,'/'+key,lambda m,k=key:received(k,m),qos_profile_sensor_data) for key,typ in [('clock',Clock),('scan',LaserScan),('odom',Odometry)]]
    for wheel in ['left_wheel_joint','right_wheel_joint']:
        jp=stage.GetPrimAtPath(root+'/Physics/'+wheel)
        drive=UsdPhysics.DriveAPI.Apply(jp,'angular')
        print('ORIGINAL_DRIVE',wheel,drive.GetStiffnessAttr().Get(),drive.GetDampingAttr().Get(),drive.GetMaxForceAttr().Get(),flush=True)
        drive.CreateStiffnessAttr(0.0);drive.CreateDampingAttr(100000.0);drive.CreateMaxForceAttr(100000000.0)
    static_meshes=[p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh) and str(p.GetPath()).startswith('/World/IC_building_scene')]
    for prim in static_meshes:
        UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
        UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr('none')
    print('COURSE601_BUILDING_COLLIDERS_READY',len(static_meshes),flush=True)
    world.reset()
    from isaacsim.core.prims import SingleArticulation
    robot=SingleArticulation(prim_path=root,name='ic382_robot_probe')
    robot.initialize()
    robot.get_articulation_controller().set_gains(kps=__import__('numpy').zeros(len(robot.dof_names)),kds=__import__('numpy').full(len(robot.dof_names),100.*setup['scene_scale']))
    from tf2_msgs.msg import TFMessage
    from geometry_msgs.msg import TransformStamped
    from rclpy.qos import QoSProfile,DurabilityPolicy
    team_footprint_pub=node.create_publisher(TFMessage,'/tf_static',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    team_footprint=TransformStamped()
    team_footprint.header.frame_id='base_link';team_footprint.child_frame_id='base_footprint'
    team_footprint.transform.translation.z=-wheel_radius
    team_footprint.transform.rotation.w=1.
    team_static_transforms=[team_footprint]
    for frame,offset in [('laser_link',[.21,0,.17]),('camera_link',[.226,0,.922])]:
        tf=TransformStamped();tf.header.frame_id='base_link';tf.child_frame_id=frame
        tf.transform.translation.x=offset[0]*setup['scene_scale']
        tf.transform.translation.y=offset[1]*setup['scene_scale']
        tf.transform.translation.z=offset[2]*setup['scene_scale']
        tf.transform.rotation.w=1.;team_static_transforms.append(tf)
    team_footprint_pub.publish(TFMessage(transforms=team_static_transforms))
    print('ROBOT_DOF_NAMES',robot.dof_names,flush=True)
    print('RUNTIME_GAINS',robot.get_articulation_controller().get_gains(),flush=True)
    from geometry_msgs.msg import Twist
    from isaacsim.core.utils.types import ArticulationAction
    command={'v':0.,'w':0.,'received':0.}
    def receive_twist(msg): command.update(v=msg.linear.x,w=msg.angular.z,received=time.time())
    cmd_sub=node.create_subscription(Twist,'/cmd_vel',receive_twist,10)
    wheel_indices=[robot.dof_names.index(n) for n in ['left_wheel_joint','right_wheel_joint']]
    from sensor_msgs.msg import JointState
    wheel_state_pub=node.create_publisher(JointState,'/joint_states',qos_profile_sensor_data)
    omni.timeline.get_timeline_interface().play()
    from pathlib import Path
    import math,numpy as np
    from isaacsim.core.utils.viewports import set_camera_view
    from omni.kit.viewport.utility import get_active_viewport,capture_viewport_to_file
    pose,_=robot.get_world_pose()
    set_camera_view(eye=pose+setup['scene_scale']*np.array([1.7,1.7,1.4]),target=pose+setup['scene_scale']*np.array([.1,0,.45]))
    start=time.time(); status_time=0; captured=False
    print('COURSE601_ORIGINAL_GPU_LIDAR_SELECTED',flush=True)
    print('IC382_COURSE601_SIMULATION_RUNNING',flush=True)
    while app.is_running():
        frame_start=time.time(); app.update()
        request=Path('/workspace/logs/course601-runtime-request.py')
        if request.exists():
            code=request.read_text();request.unlink()
            try: exec(code,globals())
            except Exception: traceback.print_exc()
        for _ in range(6): team_executor.spin_once(timeout_sec=0.0)
        encoder_time=float(og.Controller.attribute('/World/IC382_ROS2/Time.outputs:simulationTime').get())
        encoders=JointState();encoders.header.frame_id='base_link'
        encoders.header.stamp.sec=int(encoder_time)
        encoders.header.stamp.nanosec=int((encoder_time-int(encoder_time))*1e9)
        encoders.name=['left_wheel_joint','right_wheel_joint']
        encoders.position=[float(robot.get_joint_positions()[i]) for i in wheel_indices]
        encoders.velocity=[float(robot.get_joint_velocities()[i]) for i in wheel_indices]
        wheel_state_pub.publish(encoders)
        v=command['v'] if time.time()-command['received']<1.0 else 0.
        w=command['w'] if time.time()-command['received']<1.0 else 0.
        speeds=np.array([(v-wheel_track*w/2)/wheel_radius,(v+wheel_track*w/2)/wheel_radius])
        robot.apply_action(ArticulationAction(joint_velocities=speeds,joint_indices=wheel_indices))
        if time.time()-status_time>=1:
            world_pose,world_quat=robot.get_world_pose()
            state={'robot_source':setup['source'],'robot_setup':setup,'received_cmd':command,'applied_wheels':speeds.tolist(),'drive_linear':og.Controller.attribute('/World/IC382_ROS2/Drive.inputs:linearVelocity').get(),'drive_angular':og.Controller.attribute('/World/IC382_ROS2/Drive.inputs:angularVelocity').get(),'wheel_command':list(og.Controller.attribute('/World/IC382_ROS2/Drive.outputs:velocityCommand').get()),'joint_velocities':[float(v) for v in robot.get_joint_velocities()],'counts':counts,'world_pose':[float(v) for v in world_pose],'world_orientation':[float(v) for v in world_quat],'wall_elapsed':time.time()-start}
            if 'odom' in last:
                odom=last['odom']; p=odom.pose.pose.position; q=odom.pose.pose.orientation
                state['odom']={'position':[p.x,p.y,p.z],'orientation':[q.x,q.y,q.z,q.w]}
            if 'clock' in last: state['sim_time']=last['clock'].clock.sec+last['clock'].clock.nanosec/1e9
            if 'scan' in last:
                scan=last['scan']; state['scan']={'stamp':scan.header.stamp.sec+scan.header.stamp.nanosec/1e9,'frame':scan.header.frame_id,'count':len(scan.ranges),'angle_min':scan.angle_min,'angle_max':scan.angle_max,'angle_increment':scan.angle_increment,'range_min':scan.range_min,'range_max':scan.range_max,'ranges':[float(v) if math.isfinite(v) else None for v in scan.ranges]}
            tmp=Path('/workspace/logs/course601-live.json.tmp'); tmp.write_text(json.dumps(state)); tmp.replace('/workspace/logs/course601-live.json')
            status_time=time.time()
        if not captured and counts['scan']>20:
            capture_viewport_to_file(get_active_viewport(),'/workspace/logs/course601-scene.png'); captured=True
        time.sleep(max(0.,1/60-(time.time()-frame_start)))
    scan=last.get('scan')
    result={'counts':counts,'sensor':'course-original-OmniLidar','finite_returns':sum(math.isfinite(v) for v in scan.ranges) if scan else 0,'ray_count':len(scan.ranges) if scan else 0}
    Path('/workspace/logs/course601-rtx-result.json').write_text(json.dumps(result,indent=2))
    print('COURSE_ORIGINAL_RTX_RESULT',result,flush=True)
    print('COURSE_ORIGINAL_RTX_PASSED' if counts['scan']>20 and result['finite_returns']>0 else 'COURSE_ORIGINAL_RTX_FAILED',flush=True)
    omni.timeline.get_timeline_interface().stop(); node.destroy_node(); rclpy.shutdown(context=probe_context)
except Exception:
    traceback.print_exc(); print('IC382_COURSE601_NATIVE_SCENE_FAILED',flush=True)
finally: app.close()
