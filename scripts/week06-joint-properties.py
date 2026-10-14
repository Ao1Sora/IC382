from pxr import Usd,UsdPhysics
s=Usd.Stage.Open('/workspace/dev/Collected_final_wheeltec_with_scene/final_wheeltec_hpc45_clean.usdc')
for p in s.Traverse():
 if p.IsA(UsdPhysics.Joint) or (p.HasAPI(UsdPhysics.RigidBodyAPI) and 'senior_diff_robot' in str(p.GetPath())):
  print(str(p.GetPath()),flush=True)
  for a in p.GetAttributes():
   if a.HasAuthoredValueOpinion() and any(k in a.GetName() for k in ['drive:','physics:','physx','xformOp:scale']): print(a.GetName(),a.Get(),flush=True)
