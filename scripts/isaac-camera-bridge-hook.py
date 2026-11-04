"""One-shot Isaac Sim runtime request: add RGB/depth/camera_info publishers.

The running team-robot-simulation.py loop executes
/workspace/logs/course601-runtime-request.py with its own globals. Copy this
file there (or run scripts/isaac-camera-bridge.sh on the HPC host); it reuses
its ``stage``, ``base``, ``Sdf``, ``Gf``, ``UsdGeom`` and ``og`` variables.

The camera is a child of the existing base_link/camera_link mount. Its local
rotation makes the USD camera look along base_link +X with +Z up, so the image
matches the robot's forward view. ROS2CameraInfoHelper derives fx/fy from the
focal length and aperture, so no manual intrinsics are needed.
"""
if not globals().get("_ic382_camera_bridge_ready"):
    from pxr import Gf, Sdf, UsdGeom
    import omni.graph.core as og

    camera_path = base + "/camera_link/Camera"
    camera = UsdGeom.Camera.Define(stage, camera_path)
    camera.CreateFocalLengthAttr(18.0)
    camera.CreateHorizontalApertureAttr(20.955)
    camera.CreateVerticalApertureAttr(15.716)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.05, 1000.0))

    orientation = Gf.Quatf(0.5, Gf.Vec3f(0.5, -0.5, -0.5))
    orient_attr = camera.GetPrim().GetAttribute("xformOp:orient")
    if orient_attr:
        orient_attr.Set(orientation)
    else:
        UsdGeom.Xformable(camera.GetPrim()).AddOrientOp().Set(orientation)

    keys = og.Controller.Keys
    nodes = [
        ("CameraProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CameraRgb", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CameraDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CameraInfo", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
    ]
    edges = [
        ("Tick.outputs:tick", "CameraProduct.inputs:execIn"),
        ("CameraProduct.outputs:execOut", "CameraRgb.inputs:execIn"),
        ("CameraProduct.outputs:execOut", "CameraDepth.inputs:execIn"),
        ("CameraProduct.outputs:execOut", "CameraInfo.inputs:execIn"),
        ("CameraProduct.outputs:renderProductPath",
         "CameraRgb.inputs:renderProductPath"),
        ("CameraProduct.outputs:renderProductPath",
         "CameraDepth.inputs:renderProductPath"),
        ("CameraProduct.outputs:renderProductPath",
         "CameraInfo.inputs:renderProductPath"),
        ("Context.outputs:context", "CameraRgb.inputs:context"),
        ("Context.outputs:context", "CameraDepth.inputs:context"),
        ("Context.outputs:context", "CameraInfo.inputs:context"),
    ]
    values = [
        ("CameraProduct.inputs:cameraPrim", [Sdf.Path(camera_path)]),
        ("CameraProduct.inputs:width", 640),
        ("CameraProduct.inputs:height", 480),
        ("CameraRgb.inputs:type", "rgb"),
        ("CameraRgb.inputs:topicName", "/camera/color/image_raw"),
        ("CameraRgb.inputs:frameId", "camera_link"),
        ("CameraDepth.inputs:type", "depth"),
        ("CameraDepth.inputs:topicName", "/camera/depth/image_raw"),
        ("CameraDepth.inputs:frameId", "camera_link"),
        ("CameraInfo.inputs:topicName", "/camera/color/camera_info"),
        ("CameraInfo.inputs:frameId", "camera_link"),
    ]
    og.Controller.edit(
        {"graph_path": "/World/IC382_ROS2", "evaluator_name": "execution"},
        {keys.CREATE_NODES: nodes, keys.CONNECT: edges, keys.SET_VALUES: values},
    )
    globals()["_ic382_camera_bridge_ready"] = True
    print(
        "IC382_CAMERA_BRIDGE_READY "
        "/camera/color/image_raw /camera/depth/image_raw "
        "/camera/color/camera_info frame=camera_link",
        flush=True,
    )
