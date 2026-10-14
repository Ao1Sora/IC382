import os
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 1280, "height": 720, "extra_args": ["--/plugins/carb.tasking.plugin/threadCount=6", "--/plugins/omni.tbb.globalcontrol/maxThreadCount=6", "--/persistent/physics/numThreads=6"]})
try:
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid
    import numpy as np
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    cube = world.scene.add(DynamicCuboid(prim_path="/World/TestCube", name="test_cube", position=np.array([0.0, 0.0, 1.0]), scale=np.array([0.25, 0.25, 0.25])))
    world.reset()
    for _ in range(60):
        world.step(render=True)
    position, _ = cube.get_world_pose()
    if not (0.10 < position[2] < 0.20):
        raise RuntimeError(f"Unexpected settled cube position: {position}")
    print(f"IC382_SMOKE_TEST_PASSED position={position.tolist()}", flush=True)
finally:
    app.close()
