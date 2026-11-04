#!/usr/bin/env python3
"""Run YOLO26n on a folder of images and save annotated results.

This is the standalone smoke test for Isaac Sim captures; it does not need ROS2
or Isaac Sim. Install ultralytics in a normal Python venv, not in Isaac Sim's
own Python.
"""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ros2_ws" / "src" / "ic382_perception"))

from ic382_perception.model_profile import resolve_profile  # noqa: E402

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def collect_images(value):
    path = Path(value).expanduser()
    if path.is_dir():
        return sorted(
            item for item in path.rglob("*")
            if item.suffix.lower() in IMAGE_SUFFIXES
        )
    matches = sorted(Path(item) for item in glob.glob(value, recursive=True))
    return [item for item in matches if item.suffix.lower() in IMAGE_SUFFIXES]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True, help="directory or glob")
    parser.add_argument("--weights", default="yolo26n.pt")
    parser.add_argument("--output", default="annotated")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="")
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--profile", default="auto",
                        choices=["auto", "coco_bootstrap", "steward_v1"])
    args = parser.parse_args()

    images = collect_images(args.images)
    if not images:
        raise SystemExit("No images found: " + args.images)

    import cv2
    from ultralytics import YOLO

    output = Path(args.output).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.weights)
    names = {int(key): str(value) for key, value in (model.names or {}).items()}
    profile = resolve_profile(args.profile, names)

    predict_args = {
        "conf": args.conf,
        "imgsz": args.imgsz,
        "verbose": False,
    }
    if args.device:
        predict_args["device"] = args.device
    if args.half:
        predict_args["half"] = True

    class_counts = Counter()
    role_counts = Counter()
    records = []
    print(json.dumps({
        "weights": args.weights,
        "profile": profile.name,
        "tagging_enabled": profile.tagging_enabled,
        "degraded_reason": profile.degraded_reason,
        "images": len(images),
    }, ensure_ascii=False))

    for image_path in images:
        image = cv2.imread(str(image_path))
        if image is None:
            print("WARN cannot read:", image_path)
            continue
        result = model.predict(source=image, **predict_args)[0]
        detections = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = names.get(class_id, str(class_id))
            role = profile.role_for(class_id)
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            detections.append({
                "class_id": class_id,
                "class_name": class_name,
                "role": role,
                "confidence": round(confidence, 4),
                "bbox_xyxy": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            })
            class_counts[class_name] += 1
            role_counts[role] += 1

        annotated = result.plot()
        target = output / (image_path.stem + "_annotated.jpg")
        cv2.imwrite(str(target), annotated)
        records.append({
            "image": str(image_path),
            "annotated": str(target),
            "detections": detections,
        })
        print("%s: %d detections" % (image_path.name, len(detections)))

    document = {
        "weights": args.weights,
        "profile": profile.name,
        "tagging_enabled": profile.tagging_enabled,
        "degraded_reason": profile.degraded_reason,
        "class_counts": dict(class_counts),
        "role_counts": dict(role_counts),
        "images": records,
    }
    json_path = output / "detections.json"
    json_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", json_path)
    print("Class counts:", dict(class_counts))
    print("Role counts:", dict(role_counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
