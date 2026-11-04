#!/usr/bin/env python3
"""Fine-tune YOLO26n on the team's five-class dataset (RTX 3080 profile)."""
import argparse
import json
from pathlib import Path


def build_train_kwargs(args):
    """Pure argument mapping, importable without torch/ultralytics."""
    return {
        "data": str(args.data),
        "epochs": int(args.epochs),
        "imgsz": int(args.imgsz),
        "batch": int(args.batch),
        "device": str(args.device),
        "workers": int(args.workers),
        "project": str(args.project),
        "name": str(args.name),
        "patience": int(args.patience),
        "seed": int(args.seed),
        "amp": not args.no_amp,
        "cos_lr": True,
        "close_mosaic": int(args.close_mosaic),
        "pretrained": True,
        "optimizer": "auto",
        "exist_ok": True,
        "plots": True,
        "mosaic": 1.0,
        "mixup": 0.1,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "degrees": 10.0,
        "translate": 0.1,
        "scale": 0.5,
        "shear": 2.0,
        "perspective": 0.0005,
        "fliplr": 0.5,
        "flipud": 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True,
                        help="dataset.yaml with five named classes")
    parser.add_argument("--weights", default="yolo26n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16,
                        help="16 on a 16 GB RTX 3080; drop to 8 and accumulate if OOM")
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--project", default="runs/detect")
    parser.add_argument("--name", default="steward_v1_yolo26n")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not Path(args.data).is_file():
        raise SystemExit("Dataset YAML not found: " + args.data)
    kwargs = build_train_kwargs(args)
    print(json.dumps({"weights": args.weights, "train": kwargs},
                     ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    from ultralytics import YOLO

    model = YOLO(args.weights)
    model.train(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
