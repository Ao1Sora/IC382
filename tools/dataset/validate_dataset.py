#!/usr/bin/env python3
"""Validate a YOLO dataset before training.

Checks: five class names, image/label pairing, label ranges, and duplicate image
hashes across train/val/test (split leakage).
"""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

import yaml

EXPECTED_NAMES = {
    0: "ic_material",
    1: "personal",
    2: "disposables",
    3: "person",
    4: "reserved_card",
}


def image_key(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def label_path_for(image, images_root, labels_root):
    image = Path(image)
    relative = image.relative_to(images_root)
    return Path(labels_root) / relative.with_suffix(".txt")


def validate_split(split, root, names, hashes, errors):
    images_root = Path(root) / "images" / split
    labels_root = Path(root) / "labels" / split
    if not images_root.is_dir():
        errors.append("Missing image split: " + str(images_root))
        return Counter()
    counts = Counter()
    for image in sorted(images_root.rglob("*")):
        if image.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            continue
        key = image_key(image)
        if key in hashes:
            errors.append("Duplicate image across splits: %s and %s"
                          % (hashes[key], image))
        else:
            hashes[key] = str(image)
        label = label_path_for(image, images_root, labels_root)
        if not label.is_file():
            errors.append("Missing label: " + str(label))
            continue
        for line_number, line in enumerate(
                label.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            fields = line.split()
            if len(fields) != 5:
                errors.append("%s:%d expected 5 fields" % (label, line_number))
                continue
            try:
                class_id = int(fields[0])
                x, y, w, h = (float(value) for value in fields[1:])
            except ValueError:
                errors.append("%s:%d non-numeric field" % (label, line_number))
                continue
            if class_id not in names:
                errors.append("%s:%d class id %d not in names"
                              % (label, line_number, class_id))
                continue
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
                    and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                errors.append("%s:%d coordinates out of range"
                              % (label, line_number))
            counts[names[class_id]] += 1
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dataset.yaml")
    parser.add_argument("--skip-test", action="store_true")
    args = parser.parse_args()

    document = yaml.safe_load(Path(args.data).read_text(encoding="utf-8"))
    names = {int(key): str(value) for key, value in document.get("names", {}).items()}
    errors = []
    if names != EXPECTED_NAMES:
        errors.append("names must be exactly %s (got %s)" % (EXPECTED_NAMES, names))
    root = Path(document.get("path", Path(args.data).parent)).expanduser()
    if not root.is_absolute():
        root = (Path(args.data).parent / root).resolve()

    hashes = {}
    totals = Counter()
    splits = ["train", "val"] + ([] if args.skip_test else ["test"])
    for split in splits:
        totals.update(validate_split(split, root, names, hashes, errors))

    print("Dataset:", root)
    print("Instances per class:", dict(totals))
    for error in errors:
        print("ERROR:", error)
    if errors:
        return 1
    print("Dataset OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
