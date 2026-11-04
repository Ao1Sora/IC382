import os,traceback
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from pxr import Usd,Sdf,UsdGeom,UsdShade,Gf
    from pathlib import Path
    folder=Path('/workspace/dev/Collected_final_wheeltec_with_scene')
    output=folder/'final_wheeltec_hpc45.usda'
    if output.exists():
        stage=Usd.Stage.Open(str(output))
    else:
        stage=Usd.Stage.CreateNew(str(output)); stage.GetRootLayer().subLayerPaths=['final_wheeltec_with_scene.usd']
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    material=UsdShade.Material.Define(stage,'/World/IC382_HPC_Material')
    shader=UsdShade.Shader.Define(stage,'/World/IC382_HPC_Material/Shader')
    shader.CreateIdAttr('UsdPreviewSurface'); shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.65,0.68,0.72))
    shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(0.8)
    shader.CreateOutput('surface',Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
    UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath('/World')).Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants)
    lidarpath='/World/senior_diff_robot_scaled/senior_diff_robot/senior_diff_robot/Geometry/base_link/laser_link/Lidar'
    lidar=stage.GetPrimAtPath(lidarpath)
    print('ORIGINAL_LIDAR',lidar.GetTypeName(),[(a.GetName(),str(a.Get())) for a in lidar.GetAttributes()],flush=True)
    configs=list(Path('/workspace/tools/isaacsim-4.5.0/exts/isaacsim.sensors.rtx/data/lidar_configs/SLAMTEC').glob('*.json'))
    print('AVAILABLE_PLANAR_LIDAR_CONFIGS',[p.stem for p in configs],flush=True)
    if lidar.GetTypeName()!='Camera':
        camera=UsdGeom.Camera.Define(stage,lidarpath)
        for name,value in [('cameraSensorType','lidar'),('sensorModelPluginName','omni.sensors.nv.lidar.lidar_core.plugin'),('sensorModelConfig','SLAMTEC/'+configs[0].stem)]:
            camera.GetPrim().CreateAttribute(name,Sdf.ValueTypeNames.String).Set(value)
        camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.05,1000000.0))
    stage.GetRootLayer().Save()
    print('IC382_WEEK06_COMPATIBLE_SCENE_CREATED',str(output),flush=True)
except Exception:
    traceback.print_exc(); print('COMPATIBLE_SCENE_CREATE_FAILED',flush=True)
finally: app.close()
