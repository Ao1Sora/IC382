# Real-photo capture and Roboflow protocol

## Capture

- Per announced object type: 10–20 photos (not per physical instance).
- Two lighting sessions: lights on / lights off or evening; avoid a single
  lighting condition.
- Three viewpoints: front, 45° top-down, side; two distances: 0.5 m and 1.0 m.
- Include partial occlusion by another object, table edges, and shadows.
- Include empty-desk and out-of-scope-object negatives.
- Use the robot's Astra Pro at roughly the mounted height; record height, tilt,
  and intrinsics in `session.yaml`.
- Keep originals. Do not crop, rotate, or mirror before Roboflow. Apply
  augmentation only to the training split.

## Roboflow schema

Exactly five classes, this order:

```
0 ic_material
1 personal
2 disposables
3 person
4 reserved_card
```

- One tight box per object. Occluded objects include the visible extent.
- Person boxes include the full visible body/upper body.
- `reserved_card` includes the stand.
- Do not label objects with <20% visibility.
- Review twice, then export YOLO format (YOLO26 if available, otherwise YOLO).

## Export checks

- Verify `data.yaml` names and order; the runtime maps by name, so an order
  change cannot silently mis-tag, but training still needs the exact order.
- Copy the export into `datasets/combined_v1` and run
  `python tools/dataset/validate_dataset.py --data .../dataset.yaml`.
