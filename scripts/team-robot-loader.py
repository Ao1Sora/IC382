"""Install the team's CAD robot into the existing course scene."""
import json
from pathlib import Path
from pxr import Gf, Sdf, UsdGeom


def install_team_robot(stage, old_root, old_base):
    asset = Path('/workspace/robots/team_robot_20261013/team_robot.usdc')
    if not asset.is_file():
        raise FileNotFoundError(str(asset))
    cache = UsdGeom.XformCache()
    old_body_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(old_base))
    wheels = [cache.GetLocalToWorldTransform(stage.GetPrimAtPath(old_base + '/' + name))
              for name in ['left_wheel_link', 'right_wheel_link']]
    centers = [m.ExtractTranslation() for m in wheels]
    center = (centers[0] + centers[1]) * .5
    scale = Gf.Vec3d(wheels[0][0][0], wheels[0][0][1], wheels[0][0][2]).GetLength()
    if not .01 <= scale <= 100:
        raise ValueError('Unexpected legacy scene scale: ' + str(scale))
    orientation = Gf.Transform(old_body_matrix).GetRotation().GetQuat()
    if abs(scale-10.)<1e-4:
        asset=asset.with_name('team_robot_scene.usdc')
        instance_scale=1.
    else:
        instance_scale=scale
    root = '/World/TeamRobot'
    x = UsdGeom.Xform.Define(stage, root)
    x.GetPrim().GetReferences().AddReference(str(asset), '/TeamRobot')
    x.AddTranslateOp().Set(center)
    x.AddOrientOp().Set(Gf.Quatf(orientation))
    x.AddScaleOp().Set(Gf.Vec3f(instance_scale, instance_scale, instance_scale))
    stage.GetPrimAtPath(old_root).SetActive(False)
    result = dict(root=root, base=root + '/base_link', articulation=root,
                  wheel_radius=.063 * scale, wheel_track=.349 * scale,
                  scene_scale=scale, source='team_robot_20261013', spawn=list(center),
                  sensor_frames=[root+'/base_link/laser_link',root+'/base_link/camera_link',
                                 root+'/left_wheel_link',root+'/right_wheel_link'])
    Path('/workspace/logs/team-robot-setup.json').write_text(json.dumps(result,indent=2))
    print('TEAM_ROBOT_CAD_LOADED ' + json.dumps(result), flush=True)
    return result
