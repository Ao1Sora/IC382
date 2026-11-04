#!/usr/bin/env python3
"""Combine synthetic and real YOLO data into one training tree.

Synthetic data is split by its parent folder (scene/arrangement) to avoid
leakage. Real data is split by capture folder and oversampled in train so that
10-20 real photos per class are not drowned by synthetic images.
"""
import argparse
import hashlib
import random
import shutil
from pathlib import Path

import yaml

NAMES = {
    0: "ic_material",
    1: "personal",
    2: "disposables",
    3: "person",
    4: "reserved_card",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def pairs(images_root):
    root = Path(images_root)
    for image in sorted(root.rglob("*")):
        if image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        label = image.with_suffix(".txt")
        if not label.is_file():
            raise SystemExit("Missing label for " + str(image))
        yield image, label


def group_key(image, root):
    relative = image.relative_to(root)
    return relative.parts[0] if len(relative.parts) > 1 else image.stem


def deterministic_order(images, seed):
    decorated = [
        (hashlib.sha256((str(image) + str(seed)).encode()).hexdigest(), image)
        for image in images
    ]
    decorated.sort(key=lambda item: item[0])
    return [image for _, image in decorated]


def split_groups(images, root, val_fraction, test_fraction):
    groups = {}
    for image in images:
        groups.setdefault(group_key(image, root), []).append(image)
    keys = sorted(groups)
    val_count = max(1, int(round(len(keys) * val_fraction)))
    test_count = max(1, int(round(len(keys) * test_fraction)))
    val_keys = set(keys[:val_count])
    test_keys = set(keys[val_count:val_count + test_count])
    splits = {"train": [], "val": [], "test": []}
    for key, values in groups.items():
        split = "val" if key in val_keys else "test" if key in test_keys else "train"
        splits[split].extend(values)
    return splits


def copy_pairs(items, output, split, prefix, repeat=1):
    images_dir = Path(output) / "images" / split
    labels_dir = Path(output) / "labels" / split
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    for image, label in items:
        for index in range(repeat):
            stem = prefix + image.stem + ("_r%d" % index if repeat > 1 else "")
            shutil.copy2(image, images_dir / (stem + image.suffix.lower()))
            shutil.copy2(label, labels_dir / (stem + ".txt"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", required=True, help="synthetic images root")
    parser.add_argument("--real", required=True, help="real images root")
    parser.add_argument("--output", required=True)
    parser.add_argument("--real-repeat", type=int, default=5)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--test-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    random.seed(args.seed)
    sim_root, real_root = Path(args.sim), Path(args.real)
    sim_images = deterministic_order([image for image, _ in pairs(sim_root)], args.seed)
    real_images = deterministic_order([image for image, _ in pairs(real_root)], args.seed)
    if not sim_images and not real_images:
        raise SystemExit("No images found")

    sim_pairs = dict(pairs(sim_root))
    real_pairs = dict(pairs(real_root))
    sim_splits = split_groups(sim_images, sim_root, args.val_fraction, args.test_fraction)
    real_splits = split_groups(real_images, real_root, args.val_fraction, args.test_fraction)

    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    for split in ("train", "val", "test"):
        copy_pairs([(image, sim_pairs[image]) for image in sim_splits[split]],
                   output, split, "sim_")
        repeat = args.real_repeat if split == "train" else 1
        copy_pairs([(image, real_pairs[image]) for image in real_splits[split]],
                   output, split, "real_", repeat=repeat)

    document = {
        "path": str(output.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": NAMES,
    }
    (output / "dataset.yaml").write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    print("Wrote", output / "dataset.yaml")
    print("Counts:", {
        split: len(list((output / "images" / split).iterdir()))
        for split in ("train", "val", "test")
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
