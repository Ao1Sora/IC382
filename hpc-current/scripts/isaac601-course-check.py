import os,time,json,faulthandler
faulthandler.enable();faulthandler.dump_traceback_later(180,repeat=True)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'limit_cpu_threads':6,'width':640,'height':480,'extra_args':['--/rtx/verifyDriverVersion/enabled=false']})
status=1
try:
    from isaacsim.core.utils.extensions import enable_extension
    enable_extension('isaacsim.ros2.bridge')
    import omni.usd,omni.timeline
    print('COURSE601_ORIGINAL_SCENE_OPEN_BEGIN',flush=True)
    source='/workspace/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd'
    context=omni.usd.get_context();context.open_stage(source)
    for _ in range(30):app.update()
    stage=context.get_stage()
    if stage is None:raise RuntimeError('Original course stage did not load')
    graph_nodes=[]
    for prim in stage.Traverse():
        typ=prim.GetAttribute('node:type')
        if typ and typ.HasAuthoredValueOpinion():
            node_type=typ.Get();graph_nodes.append((str(prim.GetPath()),node_type))
            if 'ROS2Context' in str(node_type):
                attr=prim.GetAttribute('inputs:domain_id')
                if attr:attr.Set(82)
    print('COURSE601_ORIGINAL_SCENE_LOADED',len(graph_nodes),graph_nodes,flush=True)
    import rclpy
    from rosgraph_msgs.msg import Clock
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from rclpy.qos import qos_profile_sensor_data
    rclpy.init();node=rclpy.create_node('ic382_course601_original_probe')
    counts={'clock':0,'odom':0,'scan':0}
    def received(key,msg):counts[key]+=1
    subs=[node.create_subscription(typ,'/'+key,lambda msg,k=key:received(k,msg),qos_profile_sensor_data) for key,typ in [('clock',Clock),('odom',Odometry),('scan',LaserScan)]]
    timeline=omni.timeline.get_timeline_interface();timeline.play()
    end=time.monotonic()+30
    while time.monotonic()<end:
        app.update();rclpy.spin_once(node,timeout_sec=0.)
    print('COURSE601_ORIGINAL_TOPICS',node.get_topic_names_and_types(),flush=True)
    print('COURSE601_ORIGINAL_MESSAGE_COUNTS',counts,flush=True)
    import omni.replicator.core as rep
    import numpy as np
    from PIL import Image
    camera=rep.create.camera(position=(10,10,15),look_at=(0,0,0))
    product=rep.create.render_product(camera,(640,480))
    rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([product])
    for _ in range(3):rep.orchestrator.step(rt_subframes=4,pause_timeline=False)
    data=rgb.get_data()
    if not isinstance(data,np.ndarray) or data.shape!=(480,640,4):raise RuntimeError('Course scene did not render')
    Image.fromarray(data).save('/workspace/logs/course601-original-scene.png')
    print('COURSE601_ORIGINAL_RENDER_PASSED',data.shape,flush=True)
    node.destroy_node();rclpy.shutdown()
    if not all(counts.values()):raise RuntimeError('Original scene ROS topics incomplete: '+str(counts))
    print('IC382_COURSE601_ORIGINAL_SCENE_PASSED',flush=True);status=0
except Exception as exc:print('IC382_COURSE601_ORIGINAL_SCENE_FAILED',repr(exc),flush=True)
finally:faulthandler.cancel_dump_traceback_later();app.close(exit_code=status)
