#!/usr/bin/env python3
"""Invoke the course Isaac Sim generator and record provenance.

This wrapper does not ship teacher assets. It requires the course script and
scene to be available on the Isaac Sim host.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--course-script", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--images", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--python", default=sys.executable,
                        help="Isaac Sim python.sh on the generation host")
    parser.add_argument("--extra", action="append", default=[],
                        help="extra KEY=VALUE passed to the course script")
    args = parser.parse_args()

    script = Path(args.course_script).expanduser()
    scene = Path(args.scene).expanduser()
    if not script.is_file():
        raise SystemExit("Course generator not found: " + str(script))
    if not scene.is_file():
        raise SystemExit("Scene USD not found: " + str(scene))

    output = Path(args.output).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        "IC382_SCENE": str(scene),
        "IC382_OUTPUT": str(output),
        "IC382_IMAGES": str(args.images),
        "IC382_SEED": str(args.seed),
    })
    for item in args.extra:
        if "=" not in item:
            raise SystemExit("--extra expects KEY=VALUE")
        key, value = item.split("=", 1)
        environment[key] = value

    command = [args.python, str(script)]
    print("Running:", " ".join(command))
    subprocess.run(command, check=True, env=environment, cwd=str(script.parent))

    provenance = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scene": str(scene),
        "scene_sha256": sha256(scene),
        "course_script": str(script),
        "course_script_sha256": sha256(script),
        "images": args.images,
        "seed": args.seed,
        "python": args.python,
        "extra": args.extra,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")
    print("Provenance written to", output / "provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
