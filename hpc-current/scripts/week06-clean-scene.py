import traceback
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from pxr import Usd,Sdf
    folder='/workspace/dev/Collected_final_wheeltec_with_scene/'
    stage=Usd.Stage.Open(folder+'final_wheeltec_hpc45_flat.usdc')
    remove=[]
    for p in stage.Traverse():
        if p.GetTypeName() in ('OmniGraph','OmniGraphNode','RenderProduct','RenderSettings'):
            remove.append(str(p.GetPath()))
        if p.GetName()=='Lidar':
            print('LIDAR_API_BEFORE',p.GetAppliedSchemas(),flush=True)
            p.SetMetadata('apiSchemas',Sdf.TokenListOp.CreateExplicit([]))
            for attr in list(p.GetAttributes()):
                if attr.GetName().startswith(('omni:sensor:','_replicator:')): p.RemoveProperty(attr.GetName())
    stage.RemovePrim('/Render')
    stage.RemovePrim('/World/senior_diff_robot_scaled/senior_diff_robot/Graph')
    for path in sorted(remove,key=len,reverse=True): stage.RemovePrim(path)
    output=folder+'final_wheeltec_hpc45_clean.usdc'
    stage.GetRootLayer().Export(output)
    print('IC382_WEEK06_CLEAN_SCENE_CREATED',len(remove),output,flush=True)
except Exception: traceback.print_exc()
finally: app.close()
