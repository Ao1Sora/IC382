import traceback
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from pxr import Usd,UsdShade,Sdf
    path='/workspace/dev/Collected_final_wheeltec_with_scene/'
    stage=Usd.Stage.Open(path+'final_wheeltec_hpc45.usda')
    print('FLATTEN_START',flush=True)
    flat=stage.Flatten()
    flat.Export(path+'final_wheeltec_hpc45_flat.usdc')
    print('IC382_WEEK06_FLATTENED_SCENE_CREATED',flush=True)
except Exception: traceback.print_exc()
finally: app.close()
