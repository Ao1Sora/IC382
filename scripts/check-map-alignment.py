#!/usr/bin/env python3
"""Independent scene-ground-truth diagnostic, never a navigation/localization source."""
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

root = Path('/workspace')
d = json.loads((root/'logs/course601-live.json').read_text())
image = np.asarray(Image.open(root/'output/maps/teacher-scene-20261021/scene_map.pgm'))
distances = distance_transform_edt(image != 0) * .25
q = d['world_orientation']
yaw = math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]**2+q[3]**2))
scan = d['scan']
points = []
for i, r in enumerate(scan['ranges']):
    if r is None or not scan['range_min'] <= r <= 200.:
        continue
    a = scan['angle_min'] + i*scan['angle_increment']
    x, y = 2.1 + r*math.cos(a), r*math.sin(a)
    wx = d['world_pose'][0] + math.cos(yaw)*x - math.sin(yaw)*y
    wy = d['world_pose'][1] + math.sin(yaw)*x + math.cos(yaw)*y
    col, row = int((wx+392.)/.25), image.shape[0]-1-int((wy+80.)/.25)
    if 0 <= row < image.shape[0] and 0 <= col < image.shape[1]:
        points.append((wx, wy, float(distances[row, col])))
errors = np.array([p[2] for p in points])
result = {'method': 'independent ground truth endpoint diagnostic; not fed to AMCL',
          'world_pose': d['world_pose'], 'yaw': yaw, 'endpoints_inside_map': len(points),
          'median_obstacle_distance_scene': float(np.median(errors)),
          'p90_obstacle_distance_scene': float(np.percentile(errors, 90)),
          'fraction_within_1_scene_unit': float(np.mean(errors <= 1.0)),
          'endpoints': points}
out = root/'navigation-mvp/results'
out.mkdir(exist_ok=True)
(out/'map-alignment.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k != 'endpoints'}, indent=2))
