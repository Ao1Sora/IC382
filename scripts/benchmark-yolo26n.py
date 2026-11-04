#!/usr/bin/env python3
"""Measure YOLO26n latency/FPS on the current machine (run on the Jetson)."""
import argparse
import json
import statistics
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help=".pt, .onnx or .engine")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--device", default="0")
    parser.add_argument("--half", action="store_true")
    args = parser.parse_args()

    import numpy as np
    from ultralytics import YOLO

    model = YOLO(args.model)
    frame = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)
    kwargs = {"imgsz": args.imgsz, "device": args.device,
              "conf": 0.25, "verbose": False}
    if args.half:
        kwargs["half"] = True

    for _ in range(args.warmup):
        model.predict(source=frame, **kwargs)

    latencies = []
    for _ in range(args.frames):
        started = time.perf_counter()
        model.predict(source=frame, **kwargs)
        latencies.append((time.perf_counter() - started) * 1000.0)

    latencies.sort()
    report = {
        "model": args.model,
        "imgsz": args.imgsz,
        "frames": args.frames,
        "mean_ms": statistics.mean(latencies),
        "p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "fps": 1000.0 / statistics.mean(latencies),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
