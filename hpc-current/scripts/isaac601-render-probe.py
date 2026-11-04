import os,faulthandler
faulthandler.enable();faulthandler.dump_traceback_later(120,repeat=True)
from isaacsim import SimulationApp
mode=os.environ.get('IC382_RENDER_MODE','PathTracing')
app=SimulationApp({'headless':True,'renderer':mode,'limit_cpu_threads':6,'width':256,'height':256,'extra_args':['--/rtx/verifyDriverVersion/enabled=false','--/rtx/pathtracing/spp=1','--/rtx/pathtracing/totalSpp=8','--/rtx/pathtracing/maxBounces=2','--/rtx/post/dlss/enabled=false']})
status=1
try:
    print('RENDER_PROBE_APP_READY',mode,flush=True)
    import omni.replicator.core as rep
    import numpy as np
    from PIL import Image
    rep.create.cube(position=(0,0,0),scale=(1,1,1))
    rep.create.light(light_type='Distant',rotation=(315,0,0),intensity=3000)
    camera=rep.create.camera(position=(3,3,3),look_at=(0,0,0))
    product=rep.create.render_product(camera,(256,256))
    annotator=rep.AnnotatorRegistry.get_annotator('rgb');annotator.attach([product])
    print('RENDER_PROBE_SCENE_READY',flush=True)
    for i in range(3):
        print('RENDER_STEP_BEGIN',i,flush=True)
        rep.orchestrator.step(rt_subframes=4,delta_time=0.,pause_timeline=False)
        print('RENDER_STEP_END',i,flush=True)
    data=annotator.get_data()
    if not isinstance(data,np.ndarray) or data.shape!=(256,256,4) or not data[:,:,3].any():raise RuntimeError('No valid rendered frame')
    Image.fromarray(data).save('/workspace/logs/course601-render-probe.png')
    print('COURSE601_RENDER_PROBE_PASSED',mode,data.shape,flush=True);status=0
except Exception as exc:
    print('COURSE601_RENDER_PROBE_FAILED',repr(exc),flush=True)
finally:
    faulthandler.cancel_dump_traceback_later();app.close(exit_code=status)
