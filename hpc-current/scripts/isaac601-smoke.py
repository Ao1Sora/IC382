import os
from isaacsim import SimulationApp
threads=int(os.environ.get('SLURM_CPUS_PER_TASK','6'))
app=SimulationApp({'headless': True,'limit_cpu_threads':threads,'width':640,'height':480,'extra_args':[f'--/plugins/carb.tasking.plugin/threadCount={threads}',f'--/plugins/omni.tbb.globalcontrol/maxThreadCount={threads}',f'--/persistent/physics/numThreads={threads}']+(['--/rtx/verifyDriverVersion/enabled=false'] if os.environ.get('IC382_ISAAC601_DRIVER_TRIAL')=='1' else [])})
exit_status=0
try:
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid
    import numpy as np
    world=World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    cube=world.scene.add(DynamicCuboid(prim_path='/World/Course601Cube',name='course601_cube',position=np.array([0.,0.,1.]),scale=np.array([.25,.25,.25])))
    world.reset()
    for _ in range(60):world.step(render=True)
    position,_=cube.get_world_pose()
    if not .10<position[2]<.20:raise RuntimeError(f'Unexpected cube position {position}')
    print('COURSE601_PHYSICS_PASSED',position.tolist(),flush=True)
    from isaacsim.sensors.camera import Camera
    camera=Camera(prim_path='/World/Course601VerificationCamera',position=np.array([2.,2.,2.]),resolution=(128,128))
    camera.initialize()
    import omni.replicator.core as rep
    for _ in range(5):
        rep.orchestrator.step(rt_subframes=4,pause_timeline=False)
        world.step(render=True)
    image=camera.get_rgba()
    if image is None or image.shape!=(128,128,4) or not image[:,:,3].any():
        print('COURSE601_GPU_FRAME_FAILED: no rendered camera image',flush=True)
        raise RuntimeError('RTX camera returned no rendered image; GPU renderer is not usable')
    print('COURSE601_GPU_FRAME_PASSED',image.shape,flush=True)
    from PIL import Image
    Image.fromarray(np.asarray(image,dtype=np.uint8)).save('/workspace/logs/course601-gpu-frame.png')
    from isaacsim.core.utils.extensions import enable_extension
    enable_extension('isaacsim.ros2.bridge')
    for _ in range(20):app.update()
    import omni.kit.app
    enabled=omni.kit.app.get_app().get_extension_manager().is_extension_enabled('isaacsim.ros2.bridge')
    print('COURSE601_BRIDGE_ENABLED',enabled,flush=True)
    if not enabled:raise RuntimeError('ROS2 bridge failed to enable')
    import rclpy,time
    from geometry_msgs.msg import Twist
    rclpy.init()
    node=rclpy.create_node('ic382_course601_probe')
    got=[]
    pub=node.create_publisher(Twist,'/ic382/course601_probe',10)
    sub=node.create_subscription(Twist,'/ic382/course601_probe',lambda msg:got.append(msg.linear.x),10)
    end=time.monotonic()+10
    while time.monotonic()<end and not got:
        msg=Twist();msg.linear.x=.125;pub.publish(msg)
        rclpy.spin_once(node,timeout_sec=.1);app.update()
    if not got:raise RuntimeError('ROS2 Humble message loopback failed')
    print('COURSE601_ROS2_HUMBLE_PASSED',got,flush=True)
    node.destroy_node();rclpy.shutdown()
    print('IC382_COURSE601_SMOKE_TEST_PASSED',flush=True)
except Exception as exc:
    exit_status=1
    print('IC382_COURSE601_SMOKE_TEST_FAILED',repr(exc),flush=True)
    raise
finally:app.close(exit_code=exit_status)
