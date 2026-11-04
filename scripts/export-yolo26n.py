#!/usr/bin/env python3
"""Export a trained checkpoint to ONNX (RTX 3080) or TensorRT (target Jetson).

TensorRT engines are platform-specific. Build them on the Jetson Orin Nano that
will run the model; the 3080 should only produce ONNX. INT8 is intentionally not
supported here because TensorRT 10.x calibration is unreliable for this project.
"""
import argparse
import platform


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--format", default="onnx", choices=["onnx", "engine"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--simplify", action="store_true")
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--device", default="0")
    parser.add_argument("--workspace", type=float, default=4.0,
                        help="TensorRT workspace in GiB")
    parser.add_argument("--allow-x86-engine", action="store_true")
    args = parser.parse_args()

    if args.format == "engine":
        machine = platform.machine().lower()
        if machine not in ("aarch64", "arm64") and not args.allow_x86_engine:
            raise SystemExit(
                "TensorRT engines must be built on the target Jetson (%s detected). "
                "Export ONNX here, copy it to the Jetson, then run this script there."
                % platform.machine())
        if not args.half:
            print("Warning: FP16 is the supported precision; add --half.")

    from ultralytics import YOLO

    export_args = {
        "format": args.format,
        "imgsz": args.imgsz,
        "device": args.device,
    }
    if args.format == "onnx":
        export_args.update({"opset": args.opset, "simplify": args.simplify})
    else:
        export_args.update({"half": True, "workspace": args.workspace})

    path = YOLO(args.weights).export(**export_args)
    print("Exported:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
