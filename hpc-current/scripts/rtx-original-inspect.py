from pxr import Usd
import json
p='/workspace/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd'
s=Usd.Stage.Open(p)
prim=s.GetPrimAtPath('/World/senior_diff_robot_scaled/senior_diff_robot/senior_diff_robot/Geometry/base_link/laser_link/Lidar')
print('COURSE_SENSOR',prim.GetTypeName(),prim.GetAppliedSchemas(),flush=True)
attrs={a.GetName():str(a.Get())[:250] for a in prim.GetAttributes()}
print(json.dumps(attrs),flush=True)
open('/workspace/logs/course-original-lidar.json','w').write(json.dumps(attrs,indent=2))
