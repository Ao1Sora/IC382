from pxr import Usd, UsdGeom, UsdPhysics
from pathlib import Path
import json
scene=Path.home()/'Desktop/IC382/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd'
stage=Usd.Stage.Open(str(scene))
print('USD_OPENED',scene,flush=True)
print('DEFAULT_PRIM',stage.GetDefaultPrim().GetPath(),'METERS_PER_UNIT',UsdGeom.GetStageMetersPerUnit(stage),flush=True)
result=[]
for prim in stage.Traverse():
    attrs={}
    for a in prim.GetAttributes():
        name=a.GetName()
        if name in ('node:type','node:typeVersion') or name.startswith('inputs:') and any(t in name.lower() for t in ['topic','frame','target','joint','wheel','radius','chassis','robot','context','renderproduct']):
            attrs[name]=str(a.Get())
    if attrs or prim.GetTypeName() in ('Camera','PhysicsScene') or prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        result.append({'path':str(prim.GetPath()),'type':prim.GetTypeName(),'attrs':attrs,'relationships':{r.GetName():[str(x) for x in r.GetTargets()] for r in prim.GetRelationships()}})
out=Path.home()/'Desktop/IC382/logs/week06-usd-inspect.json'
out.write_text(json.dumps(result,indent=2))
for item in result: print(json.dumps(item),flush=True)
print('IC382_WEEK06_USD_INSPECT_PASSED',flush=True)
