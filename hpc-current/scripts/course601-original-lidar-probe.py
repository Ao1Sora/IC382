import os,time,json,traceback,math
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'limit_cpu_threads':6,'width':128,'height':128,'extra_args':['--/rtx/verifyDriverVersion/enabled=false','--/app/extensions/registryEnabled=false']},experience='/workspace/tools/isaacsim-6.0.1/apps/isaacsim.exp.base.python.kit')
status=1
try:
 from isaacsim.core.utils.extensions import enable_extension
 enable_extension('isaacsim.ros2.bridge');enable_extension('isaacsim.sensors.rtx')
 from pxr import UsdGeom,Sdf,Gf
 import omni.usd,omni.graph.core as og,omni.timeline
 stage=omni.usd.get_context().get_stage()
 layer=Sdf.Layer.FindOrOpen('/workspace/dev/Collected_final_wheeltec_with_scene/course-original-lidar.usda')
 source='/World/senior_diff_robot_scaled/senior_diff_robot/senior_diff_robot/Geometry/base_link/laser_link/Lidar'
 Sdf.CreatePrimInLayer(stage.GetRootLayer(),'/World/Lidar');Sdf.CopySpec(layer,source,stage.GetRootLayer(),'/World/Lidar')
 prim=stage.GetPrimAtPath('/World/Lidar');prim.SetActive(True)
 print('ORIGINAL_LIDAR_PROFILE',prim.GetTypeName(),prim.GetAppliedSchemas(),flush=True)
 for pos in [(5,0,0),(0,5,0),(-5,0,0),(0,-5,0)]:
  cube=UsdGeom.Cube.Define(stage,'/World/Wall'+str(pos).replace(' ','').replace('(','').replace(')','').replace(',','_').replace('-','minus'))
  cube.CreateSizeAttr(2);cube.AddTranslateOp().Set(Gf.Vec3d(*pos))
 from isaacsim.core.api import World
 world=World(stage_units_in_meters=1);world.reset()
 k=og.Controller.Keys
 og.Controller.edit({'graph_path':'/World/ROS','evaluator_name':'execution'},{k.CREATE_NODES:[('Tick','omni.graph.action.OnPlaybackTick'),('Context','isaacsim.ros2.bridge.ROS2Context'),('Product','isaacsim.core.nodes.IsaacCreateRenderProduct'),('LidarPub','isaacsim.ros2.bridge.ROS2RtxLidarHelper')],k.CONNECT:[('Tick.outputs:tick','Product.inputs:execIn'),('Product.outputs:execOut','LidarPub.inputs:execIn'),('Product.outputs:renderProductPath','LidarPub.inputs:renderProductPath'),('Context.outputs:context','LidarPub.inputs:context')],k.SET_VALUES:[('Context.inputs:domain_id',83),('Product.inputs:cameraPrim',[Sdf.Path('/World/Lidar')]),('Product.inputs:width',128),('Product.inputs:height',1),('LidarPub.inputs:topicName','course_original_scan'),('LidarPub.inputs:frameId','laser_link'),('LidarPub.inputs:type','laser_scan')]})
 import rclpy
 from sensor_msgs.msg import LaserScan
 from rclpy.qos import qos_profile_sensor_data
 os.environ['ROS_DOMAIN_ID']='83';rclpy.init();node=rclpy.create_node('course_original_lidar_probe');samples=[]
 def received(msg):
  finite=[float(v) for v in msg.ranges if math.isfinite(v) and v>0]
  samples.append({'count':len(msg.ranges),'finite':len(finite),'min':min(finite) if finite else None,'max':max(finite) if finite else None,'range_max':msg.range_max,'frame_id':msg.header.frame_id})
 sub=node.create_subscription(LaserScan,'/course_original_scan',received,qos_profile_sensor_data)
 omni.timeline.get_timeline_interface().play();start=time.time()
 while time.time()-start<90:
  app.update();rclpy.spin_once(node,timeout_sec=0)
  if len(samples)>=30:break
 result={'sensor_type':prim.GetTypeName(),'messages':len(samples),'last_scan':samples[-1] if samples else None,'elapsed':time.time()-start}
 print('COURSE_ORIGINAL_LIDAR_PROBE_RESULT',result,flush=True)
 open('/workspace/logs/course601-original-lidar-probe.json','w').write(json.dumps(result,indent=2))
 status=0 if len(samples)>=30 and samples[-1]['finite']>0 else 1
 print('COURSE_ORIGINAL_LIDAR_PROBE_PASSED' if status==0 else 'COURSE_ORIGINAL_LIDAR_PROBE_FAILED',flush=True)
 node.destroy_node();rclpy.shutdown()
except Exception:traceback.print_exc()
finally:app.close(exit_code=status)
