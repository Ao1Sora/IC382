# YOLO26n training and deployment

## Environment (RTX 3080 16 GB)

```bash
pip install "ultralytics>=8.3.222" "numpy<2.0"
# Install the CUDA build of torch from the PyTorch index first.
```

CI does not install these; the ROS packages keep `ultralytics` lazily imported.

## Train

```bash
python scripts/train-yolo26n.py \
  --data datasets/combined_v1/dataset.yaml \
  --weights yolo26n.pt \
  --epochs 100 --imgsz 640 --batch 16 --device 0 \
  --project runs/detect --name steward_v1_yolo26n
```

If CUDA runs out of memory, reduce `--batch` to 8 before reducing `--imgsz`.
The default augmentation is mosaic/mixup/HSV/degrees/translate/scale/shear/
perspective, with `close_mosaic=10`.

## Gates (real test split is authoritative)

| Metric | Gate |
|---|---|
| Overall mAP50 | ≥ 0.85 |
| Overall mAP50-95 | ≥ 0.55 |
| `person` mAP50 / recall@0.35 | ≥ 0.85 / ≥ 0.90 |
| `reserved_card` mAP50 | ≥ 0.80 |
| A/B/C cross-confusion | ≤ 10% each |
| Empty-desk false positives | ≤ 1 per 10 frames |
| Out-of-scope objects tagged | 0 (hard) |

If yolo26n fails, switch only the weights/profile to `yolo26s`; the node code is
name-based and does not change.

## Export

RTX 3080 (ONNX only):

```bash
python scripts/export-yolo26n.py --weights runs/detect/steward_v1_yolo26n/weights/best.pt \
  --format onnx --imgsz 640 --opset 17 --simplify
```

Jetson Orin Nano (TensorRT FP16 must be built on the target):

```bash
python scripts/export-yolo26n.py --weights best.onnx \
  --format engine --imgsz 640 --half --device 0 --workspace 4
```

Verify and benchmark on the Jetson:

```bash
python scripts/check-model.py --weights /home/student/dev/models/steward_v1.engine
python scripts/benchmark-yolo26n.py --model /home/student/dev/models/steward_v1.engine --half
```

Targets: safety loop ≥15 FPS (20–25 preferred), classification ≥5 FPS,
p95 safety latency ≤80 ms, 10 minutes without thermal throttling.
