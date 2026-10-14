import os,time,traceback,json,asyncio
import omni.kit.app
kit=omni.kit.app.get_app()
async def configure_course():
    try:
        from isaacsim.core.utils.extensions import enable_extension
        for name in ['isaacsim.ros2.bridge','isaacsim.robot.wheeled_robots','isaacsim.sensors.rtx']: enable_extension(name)
        from pxr import Usd,Sdf
        from pathlib import Path
        folder=Path('/hpc/puhome/24110598d/Desktop/IC382/dev/Collected_final_wheeltec_with_scene')
        overlay=folder/'final_wheeltec_hpc45_native.usda'
        root='/World/senior_diff_robot_scaled/senior_diff_robot'
        base=root+'/senior_diff_robot/Geometry/base_link'
        overlay=folder/'final_wheeltec_hpc45_clean.usdc'
        import omni.usd,omni.timeline,omni.graph.core as og
        context=omni.usd.get_context()
        from isaacsim.core.api import World
        world=World(stage_units_in_meters=1.0)
    await world.initialize_simulation_context_async()
        stage=context.get_stage()
        stage.DefinePrim('/World','Xform').GetReferences().AddReference(str(overlay),'/World')
        for _ in range(20): await kit.next_update_async()
        print('COURSE_NATIVE_STAGE_LOADED',flush=True)
        from pxr import UsdPhysics
        import omni.isaac.IsaacSensorSchema as IsaacSensorSchema
        from pxr import Gf,UsdGeom
        import omni.kit.commands
        old_lidar=stage.GetPrimAtPath(base+'/laser_link/Lidar')
        old_lidar.SetActive(False)
        _,new_lidar=omni.kit.commands.execute('IsaacSensorCreateRtxLidar',path='/HPC_Lidar',parent=base+'/laser_link',config='SLAMTEC/RPLIDAR_S2E',translation=Gf.Vec3d(0,0,0.02),orientation=Gf.Quatd(1,0,0,0))
        print('HPC_RTX_LIDAR_CREATED',str(new_lidar.GetPath()),flush=True)
        cache=UsdGeom.XformCache()
        bodies=[p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI) and str(p.GetPath()).startswith(base+'/')]
        body_poses=[(p,cache.GetLocalToWorldTransform(p)) for p in bodies]
        for body,pose in body_poses:
            xform=UsdGeom.Xformable(body); xform.ClearXformOpOrder(); xform.SetResetXformStack(True); xform.AddTransformOp().Set(pose)
        print('HPC_RIGID_BODY_RESETS',len(body_poses),flush=True)
        for name,radius in [('left_wheel_link',0.063),('right_wheel_link',0.063),('quanxiang_wheel_link',0.063)]:
            link=base+'/'+name
            for prim in Usd.PrimRange(stage.GetPrimAtPath(link)):
                if prim.HasAPI(UsdPhysics.CollisionAPI): UsdPhysics.CollisionAPI(prim).CreateCollisionEnabledAttr(False)
            cylinder=UsdGeom.Cylinder.Define(stage,link+'/HPC_WheelCollision')
            cylinder.CreateRadiusAttr(radius);cylinder.CreateHeightAttr(0.022);cylinder.CreateAxisAttr('Y')
            cylinder.CreatePurposeAttr('guide')
            UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim())
        print('IC382_PRIMITIVE_WHEEL_COLLISIONS_CREATED',flush=True)
    
        print('USD_JOINTS',[(str(p.GetPath()),[str(t) for t in p.GetRelationship('physics:body0').GetTargets()],[str(t) for t in p.GetRelationship('physics:body1').GetTargets()]) for p in stage.Traverse() if p.IsA(UsdPhysics.Joint)],flush=True)
        keys=og.Controller.Keys
        nodes=[('Tick','omni.graph.action.OnPlaybackTick'),('Context','isaacsim.ros2.bridge.ROS2Context'),('Time','isaacsim.core.nodes.IsaacReadSimulationTime'),('Clock','isaacsim.ros2.bridge.ROS2PublishClock'),('Twist','isaacsim.ros2.bridge.ROS2SubscribeTwist'),('Linear','omni.graph.nodes.BreakVector3'),('Angular','omni.graph.nodes.BreakVector3'),('Drive','isaacsim.robot.wheeled_robots.DifferentialController'),('Articulation','isaacsim.core.nodes.IsaacArticulationController'),('Odom','isaacsim.core.nodes.IsaacComputeOdometry'),('OdomPub','isaacsim.ros2.bridge.ROS2PublishOdometry'),('OdomTF','isaacsim.ros2.bridge.ROS2PublishRawTransformTree'),('SensorTF','isaacsim.ros2.bridge.ROS2PublishTransformTree'),('LidarProduct','isaacsim.core.nodes.IsaacCreateRenderProduct'),('LidarPub','isaacsim.ros2.bridge.ROS2RtxLidarHelper')]
        edges=[]
        for node in ['Clock','Twist','Odom','SensorTF','LidarProduct']:
            edges.append(('Tick.outputs:tick',node+'.inputs:execIn'))
        for node in ['Clock','Twist','OdomPub','OdomTF','SensorTF','LidarPub']:
            edges.append(('Context.outputs:context',node+'.inputs:context'))
        edges += [('Twist.outputs:execOut','Drive.inputs:execIn'),('Time.outputs:simulationTime','Clock.inputs:timeStamp'),('Twist.outputs:linearVelocity','Linear.inputs:tuple'),('Twist.outputs:angularVelocity','Angular.inputs:tuple'),('Linear.outputs:x','Drive.inputs:linearVelocity'),('Angular.outputs:z','Drive.inputs:angularVelocity'),('Drive.outputs:velocityCommand','Articulation.inputs:velocityCommand'),('Odom.outputs:execOut','OdomPub.inputs:execIn'),('Odom.outputs:execOut','OdomTF.inputs:execIn'),('Odom.outputs:position','OdomPub.inputs:position'),('Odom.outputs:orientation','OdomPub.inputs:orientation'),('Odom.outputs:linearVelocity','OdomPub.inputs:linearVelocity'),('Odom.outputs:angularVelocity','OdomPub.inputs:angularVelocity'),('Odom.outputs:position','OdomTF.inputs:translation'),('Odom.outputs:orientation','OdomTF.inputs:rotation'),('Time.outputs:simulationTime','OdomPub.inputs:timeStamp'),('Time.outputs:simulationTime','OdomTF.inputs:timeStamp'),('Time.outputs:simulationTime','SensorTF.inputs:timeStamp'),('LidarProduct.outputs:execOut','LidarPub.inputs:execIn'),('LidarProduct.outputs:renderProductPath','LidarPub.inputs:renderProductPath')]
        values=[('Context.inputs:domain_id',82),('Twist.inputs:topicName','cmd_vel'),('Drive.inputs:wheelRadius',0.63),('Drive.inputs:wheelDistance',3.627),('Articulation.inputs:jointNames',['left_wheel_joint','right_wheel_joint']),('Articulation.inputs:targetPrim',[Sdf.Path(base)]),('Odom.inputs:chassisPrim',[Sdf.Path(base)]),('OdomPub.inputs:topicName','odom'),('OdomPub.inputs:odomFrameId','odom'),('OdomPub.inputs:chassisFrameId','base_link'),('OdomTF.inputs:parentFrameId','odom'),('OdomTF.inputs:childFrameId','base_link'),('SensorTF.inputs:parentPrim',[Sdf.Path(base)]),('SensorTF.inputs:targetPrims',[Sdf.Path(base+'/'+n) for n in ['laser_link','camera_link','left_wheel_link','right_wheel_link','quanxiang_wheel_link','controller_link']]),('LidarProduct.inputs:cameraPrim',[Sdf.Path(base+'/laser_link/HPC_Lidar')]),('LidarProduct.inputs:width',128),('LidarProduct.inputs:height',1),('LidarPub.inputs:topicName','scan'),('LidarPub.inputs:frameId','laser_link'),('LidarPub.inputs:type','laser_scan')]
        og.Controller.edit({'graph_path':'/World/IC382_ROS2','evaluator_name':'execution'},{keys.CREATE_NODES:nodes,keys.CONNECT:edges,keys.SET_VALUES:values})
        print('COURSE_NATIVE_GRAPH_CREATED',flush=True)
        import rclpy
        from sensor_msgs.msg import LaserScan
        from nav_msgs.msg import Odometry
        from rosgraph_msgs.msg import Clock
        from rclpy.qos import qos_profile_sensor_data
        rclpy.init(); node=rclpy.create_node('ic382_native_probe')
        counts={'clock':0,'scan':0,'odom':0}
        last={}
        def received(key,msg): counts[key]+=1; last[key]=msg
        subscriptions=[node.create_subscription(typ,'/'+key,lambda m,k=key:received(k,m),qos_profile_sensor_data) for key,typ in [('clock',Clock),('scan',LaserScan),('odom',Odometry)]]
        for wheel in ['left_wheel_joint','right_wheel_joint']:
            jp=stage.GetPrimAtPath(root+'/senior_diff_robot/Physics/'+wheel)
            drive=UsdPhysics.DriveAPI.Apply(jp,'angular')
            print('ORIGINAL_DRIVE',wheel,drive.GetStiffnessAttr().Get(),drive.GetDampingAttr().Get(),drive.GetMaxForceAttr().Get(),flush=True)
            drive.CreateStiffnessAttr(0.0);drive.CreateDampingAttr(100000.0);drive.CreateMaxForceAttr(100000000.0)
        await world.reset_async()
        from isaacsim.core.prims import SingleArticulation
        robot=SingleArticulation(prim_path=base,name='ic382_robot_probe')
        robot.initialize()
        robot.get_articulation_controller().set_gains(kps=__import__('numpy').zeros(3),kds=__import__('numpy').array([100.,100.,0.]))
        print('ROBOT_DOF_NAMES',robot.dof_names,flush=True)
        for p in stage.Traverse():
            if p.IsA(UsdPhysics.Joint) or (p.HasAPI(UsdPhysics.RigidBodyAPI) and str(p.GetPath()).startswith(base)):
                print('PHYSICS_PROPERTIES',str(p.GetPath()),[(a.GetName(),a.Get()) for a in p.GetAttributes() if a.HasAuthoredValueOpinion() and any(k in a.GetName() for k in ['drive:','physics:','physx','xformOp:scale'])],flush=True)
        print('RUNTIME_GAINS',robot.get_articulation_controller().get_gains(),flush=True)
        from geometry_msgs.msg import Twist
        from isaacsim.core.utils.types import ArticulationAction
        command={'v':0.,'w':0.,'received':0.}
        def receive_twist(msg): command.update(v=msg.linear.x,w=msg.angular.z,received=time.time())
        cmd_sub=node.create_subscription(Twist,'/cmd_vel',receive_twist,10)
        wheel_indices=[robot.dof_names.index(n) for n in ['left_wheel_joint','right_wheel_joint']]
        omni.timeline.get_timeline_interface().play()
        from pathlib import Path
        import math,numpy as np
        from isaacsim.core.utils.viewports import set_camera_view
        from omni.kit.viewport.utility import get_active_viewport,capture_viewport_to_file
        pose,_=robot.get_world_pose()
        set_camera_view(eye=pose+np.array([12.,12.,10.]),target=pose)
        start=time.time(); status_time=0; captured=False
        print('IC382_WEEK06_SIMULATION_RUNNING',flush=True)
        while kit.is_running() and time.time()-start<7200:
            frame_start=time.time(); await kit.next_update_async()
            request=Path('/hpc/puhome/24110598d/Desktop/IC382/logs/week06-runtime-request.py')
            if request.exists():
                code=request.read_text();request.unlink()
                try: exec(code,globals())
                except Exception: traceback.print_exc()
            for _ in range(6): rclpy.spin_once(node,timeout_sec=0.0)
            v=command['v'] if time.time()-command['received']<1.0 else 0.
            w=command['w'] if time.time()-command['received']<1.0 else 0.
            speeds=np.array([(v-3.627*w/2)/.63,(v+3.627*w/2)/.63])
            robot.apply_action(ArticulationAction(joint_velocities=speeds,joint_indices=wheel_indices))
            if time.time()-status_time>=1:
                world_pose,world_quat=robot.get_world_pose()
                state={'received_cmd':command,'applied_wheels':speeds.tolist(),'drive_linear':og.Controller.attribute('/World/IC382_ROS2/Drive.inputs:linearVelocity').get(),'drive_angular':og.Controller.attribute('/World/IC382_ROS2/Drive.inputs:angularVelocity').get(),'wheel_command':list(og.Controller.attribute('/World/IC382_ROS2/Drive.outputs:velocityCommand').get()),'joint_velocities':[float(v) for v in robot.get_joint_velocities()],'counts':counts,'world_pose':[float(v) for v in world_pose],'world_orientation':[float(v) for v in world_quat],'wall_elapsed':time.time()-start}
                if 'odom' in last:
                    odom=last['odom']; p=odom.pose.pose.position; q=odom.pose.pose.orientation
                    state['odom']={'position':[p.x,p.y,p.z],'orientation':[q.x,q.y,q.z,q.w]}
                if 'clock' in last: state['sim_time']=last['clock'].clock.sec+last['clock'].clock.nanosec/1e9
                if 'scan' in last:
                    scan=last['scan']; state['scan']={'stamp':scan.header.stamp.sec+scan.header.stamp.nanosec/1e9,'frame':scan.header.frame_id,'count':len(scan.ranges),'angle_min':scan.angle_min,'angle_max':scan.angle_max,'angle_increment':scan.angle_increment,'range_min':scan.range_min,'range_max':scan.range_max,'ranges':[float(v) if math.isfinite(v) else None for v in scan.ranges]}
                tmp=Path('/hpc/puhome/24110598d/Desktop/IC382/logs/week06-live.json.tmp'); tmp.write_text(json.dumps(state)); tmp.replace('/hpc/puhome/24110598d/Desktop/IC382/logs/week06-live.json')
                status_time=time.time()
            if not captured and counts['scan']>20:
                capture_viewport_to_file(get_active_viewport(),'/hpc/puhome/24110598d/Desktop/IC382/logs/week06-scene.png'); captured=True
            await asyncio.sleep(max(0.,1/60-(time.time()-frame_start)))
        print('IC382_WEEK06_SIMULATION_FINISHED',counts,flush=True)
        omni.timeline.get_timeline_interface().stop(); node.destroy_node(); rclpy.shutdown()
    except Exception:
        traceback.print_exc(); print('IC382_WEEK06_NATIVE_SCENE_FAILED',flush=True)
    finally: print('COURSE_SCRIPT_STOPPED',flush=True)

asyncio.ensure_future(configure_course())
