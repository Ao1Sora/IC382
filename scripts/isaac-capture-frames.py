"""Capture RGB frames from an Isaac Sim USD scene for a standalone YOLO test.

Run with Isaac Sim's own Python (Linux: ~/isaacsim/python.sh). This script does
not import ultralytics, so it cannot disturb Isaac Sim's Python environment.
Run scripts/yolo-infer-images.py afterwards in a normal Python venv.

Examples:
  python.sh isaac-capture-frames.py --scene scene.usdc --list-cameras
  python.sh isaac-capture-frames.py --scene scene.usdc \
      --camera-prim /World/Camera --frames 20 --output ~/ic382_frames
  python.sh isaac-capture-frames.py --scene scene.usdc \
      --position 10 10 15 --look-at 0 0 0 --frames 20 --output ~/ic382_frames
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", help="USD scene path")
    parser.add_argument("--camera-prim", default="",
                        help="existing UsdGeom.Camera prim path")
    parser.add_argument("--list-cameras", action="store_true",
                        help="open the scene and print all camera prim paths")
    parser.add_argument("--position", nargs=3, type=float,
                        default=[10.0, 10.0, 15.0])
    parser.add_argument("--look-at", nargs=3, type=float,
                        default=[0.0, 0.0, 0.0])
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", default="~/ic382_frames")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--rt-subframes", type=int, default=4)
    parser.add_argument("--load-updates", type=int, default=60)
    parser.add_argument("--repair-script", default="",
                        help="optional repair-course-scene.py path")
    parser.add_argument("--repair-cache",
                        default="~/ic382_cache/course-scene-repaired.usda")
    return parser.parse_args()


def load_stage(app, context, scene, updates):
    context.open_stage(str(scene))
    for _ in range(updates):
        app.update()
    stage = context.get_stage()
    if stage is None:
        raise RuntimeError("Stage did not load: " + str(scene))
    return stage


def main():
    args = parse_args()
    if not args.scene:
        raise SystemExit("--scene is required (or use --list-cameras with --scene)")

    from isaacsim import SimulationApp

    app = SimulationApp({
        "headless": bool(args.headless),
        "width": max(1280, args.width),
        "height": max(720, args.height),
    })
    try:
        import omni.usd
        from pxr import UsdGeom

        context = omni.usd.get_context()
        scene = Path(args.scene).expanduser()
        stage = load_stage(app, context, scene, args.load_updates)

        if args.repair_script:
            import runpy

            repair = runpy.run_path(args.repair_script)["repair_scene"]
            cache = Path(args.repair_cache).expanduser()
            repaired = repair(scene, cache, scene.parent)
            stage = load_stage(app, context, repaired, args.load_updates)
            scene = Path(repaired)

        if args.list_cameras:
            cameras = [str(prim.GetPath()) for prim in stage.Traverse()
                       if prim.IsA(UsdGeom.Camera)]
            print("IC382_CAMERAS " + json.dumps(cameras), flush=True)
            return 0

        import numpy as np
        import omni.replicator.core as rep
        import omni.timeline
        from PIL import Image

        if args.camera_prim:
            if not stage.GetPrimAtPath(args.camera_prim).IsValid():
                raise RuntimeError("Camera prim not found: " + args.camera_prim)
            camera = args.camera_prim
        else:
            camera = rep.create.camera(
                position=tuple(args.position), look_at=tuple(args.look_at))

        omni.timeline.get_timeline_interface().play()
        product = rep.create.render_product(camera, (args.width, args.height))
        rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb.attach([product])

        output = Path(args.output).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        written = 0
        for index in range(args.frames):
            rep.orchestrator.step(
                rt_subframes=args.rt_subframes, pause_timeline=False)
            data = rgb.get_data()
            if data is None:
                print("WARN frame %d not ready" % index, flush=True)
                continue
            image = np.asarray(data, dtype=np.uint8)
            if image.ndim == 3 and image.shape[2] == 4:
                image = image[:, :, :3]
            target = output / ("frame_%04d.png" % written)
            Image.fromarray(image).save(target)
            written += 1

        metadata = {
            "scene": str(scene),
            "camera_prim": args.camera_prim or None,
            "position": list(args.position),
            "look_at": list(args.look_at),
            "width": args.width,
            "height": args.height,
            "frames": written,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        (output / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8")
        print("IC382_FRAMES_CAPTURED n=%d shape=%dx%d" % (
            written, args.width, args.height), flush=True)
        return 0 if written else 1
    finally:
        app.close()


if __name__ == "__main__":
    sys.exit(main())
