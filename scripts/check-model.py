#!/usr/bin/env python3
"""Validate a YOLO checkpoint and its class-name mapping against a team profile."""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ros2_ws" / "src" / "ic382_perception"))

from ic382_perception.model_profile import resolve_profile  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, help=".pt, .onnx or .engine")
    parser.add_argument("--profile", default="auto",
                        choices=["auto", "coco_bootstrap", "steward_v1"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-infer", action="store_true")
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    names = {int(key): str(value) for key, value in (model.names or {}).items()}
    profile = resolve_profile(args.profile, names)
    report = {
        "weights": str(args.weights),
        "classes": len(names),
        "names": names,
        "profile": profile.name,
        "tagging_enabled": profile.tagging_enabled,
        "degraded_reason": profile.degraded_reason,
        "class_id_to_role": profile.class_id_to_role,
    }

    if not args.no_infer:
        import numpy as np

        frame = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)
        result = model.predict(
            source=frame, imgsz=args.imgsz, device=args.device,
            conf=0.25, verbose=False)[0]
        report["dummy_boxes"] = int(len(result.boxes))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if profile.degraded_reason:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
