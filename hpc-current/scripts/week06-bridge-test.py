import os
from isaacsim import SimulationApp
threads=int(os.environ.get('SLURM_CPUS_PER_TASK','6'))
app=SimulationApp({'headless': True, 'extra_args':[f'--/plugins/carb.tasking.plugin/threadCount={threads}',f'--/plugins/omni.tbb.globalcontrol/maxThreadCount={threads}']})
try:
    from isaacsim.core.utils.extensions import enable_extension
    enable_extension('isaacsim.ros2.bridge')
    for _ in range(20): app.update()
    import omni.kit.app
    manager=omni.kit.app.get_app().get_extension_manager()
    enabled=manager.is_extension_enabled('isaacsim.ros2.bridge')
    print('WEEK06_BRIDGE_ENABLED',enabled,flush=True)
    if not enabled: raise RuntimeError('ROS2 bridge disabled after initialization')
    import rclpy
    from geometry_msgs.msg import Twist
    rclpy.init()
    node=rclpy.create_node('ic382_bridge_probe')
    publisher=node.create_publisher(Twist,'/ic382/bridge_probe',10)
    got=[]
    subscriber=node.create_subscription(Twist,'/ic382/bridge_probe',lambda msg: got.append(msg.linear.x),10)
    import time
    end=time.time()+10
    while time.time()<end and not got:
        msg=Twist(); msg.linear.x=0.125; publisher.publish(msg)
        rclpy.spin_once(node,timeout_sec=0.1); app.update()
    print('WEEK06_RCLPY_RECEIVED',got,flush=True)
    if not got: raise RuntimeError('ROS2 message loopback failed')
    node.destroy_node(); rclpy.shutdown()
    print('IC382_WEEK06_BRIDGE_TEST_PASSED',flush=True)
finally: app.close()
