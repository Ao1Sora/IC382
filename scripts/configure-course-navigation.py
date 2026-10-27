#!/usr/bin/env python3
"""Resolve teacher Nav2 parameters plus team overrides and optional sim spawn."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import yaml

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo/'ros2_ws/src/ic382_navigation'))
from ic382_navigation.profiles import build_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', default='/workspace')
    parser.add_argument('--output', required=True)
    parser.add_argument('--teacher-params', '--base-params', dest='teacher_params',
                        default=str(repo/'teacher/ros2/config/custom_nav2_params.yaml'))
    parser.add_argument('--overrides', default=str(repo/
        'ros2_ws/src/ic382_navigation/config/nav2_team_overrides.yaml'))
    parser.add_argument('--static', action='store_true',
                        help='Generate without a simulator-specific initial pose')
    parser.add_argument('--footprint', default=None)
    args = parser.parse_args()
    baseline, overrides = Path(args.teacher_params), Path(args.overrides)
    pose = None
    if not args.static:
        live = json.loads((Path(args.environment)/'logs/course601-live.json').read_text())
        q = live['world_orientation']
        yaw = math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]**2+q[3]**2))
        pose = dict(x=live['world_pose'][0], y=live['world_pose'][1], z=0.0, yaw=yaw)
    data = build_profile(yaml.safe_load(baseline.read_text()),
                         yaml.safe_load(overrides.read_text()), pose, args.footprint)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    provenance = {'teacher_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
                  'overrides_sha256': hashlib.sha256(overrides.read_bytes()).hexdigest(),
                  'initial_pose': pose, 'scene_scale': 10.0}
    provenance['initial_pose_source'] = 'explicit_launch_configuration' if args.static else 'simulator_snapshot'
    out.with_suffix('.sources.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps({'params': str(out), **provenance}, indent=2))


if __name__ == '__main__':
    main()
