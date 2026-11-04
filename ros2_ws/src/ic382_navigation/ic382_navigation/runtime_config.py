"""Single physical-runtime configuration and convex-desk candidate generation."""
import json
import math
from pathlib import Path
from .inspection import canonical_desk, load_desks


def laser_body_footprint(bounds, laser_in_base):
    """Convert a body rectangle measured from laser into the Nav2 base frame."""
    front, back, left, right = (float(bounds[k]) for k in ('front','back','left','right'))
    if not all(math.isfinite(v) and v > 0 for v in (front,back,left,right)):
        raise ValueError('Laser-relative body dimensions must be finite and positive')
    lx, ly, yaw = laser_in_base
    c,s=math.cos(yaw),math.sin(yaw)
    return [[lx+c*x-s*y,ly+s*x+c*y] for x,y in
            [(-back,-right),(front,-right),(front,left),(-back,left)]]


def resolve_runtime(document, path):
    if document.get('schema_version') != 1:
        raise ValueError('Unsupported runtime schema_version')
    result = dict(document)
    for key in ('map', 'navigation_map', 'params_file', 'points', 'log_directory'):
        value = result.get(key, '')
        if value:
            target = Path(value).expanduser()
            result[key] = str(target if target.is_absolute() else Path(path).resolve().parent/target)
    if not isinstance(result.get('start_hardware', False), bool):
        raise ValueError('start_hardware must be a YAML boolean')
    if not isinstance(result.get('live_obstacles', True), bool):
        raise ValueError('live_obstacles must be a YAML boolean')
    if not isinstance(result.get('inflation_enabled', True), bool):
        raise ValueError('inflation_enabled must be a YAML boolean')
    return result


def generate_candidates(settings, footprint):
    gap = settings.get('parking_distance_m', .5)
    if isinstance(gap, bool) or not isinstance(gap, (int,float)) or not math.isfinite(gap) or gap <= 0:
        raise ValueError('parking_distance_m must be finite and positive')
    if settings.get('points_per_desk', 3) != 3:
        raise ValueError('The desk action currently requires exactly three inspection stops')
    footprint = settings.get('robot_footprint') or footprint
    if isinstance(footprint,str): footprint = json.loads(footprint)
    if not footprint or len(footprint) < 3 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in footprint):
        raise ValueError('A measured robot footprint polygon is required')
    # Every generated heading points the robot's +X axis toward the table.
    front = max(float(p[0]) for p in footprint)
    if front <= 0: raise ValueError('Robot footprint must extend forward of base_footprint')
    reference=settings.get('parking_reference','body_front')
    if reference not in ('body_front','laser'):
        raise ValueError('parking_reference must be body_front or laser')
    if reference=='laser':
        lx,ly,laser_yaw=settings['laser_in_base']
        if abs(laser_yaw)>1e-6:
            raise ValueError('Desk viewpoints require a forward-facing laser')
    points=[]; seen=set()
    for desk in settings.get('desks', []):
        desk_id=canonical_desk(desk['id'])
        if desk_id in seen: raise ValueError('Duplicate desk ID')
        seen.add(desk_id)
        polygon=desk['polygon']; count=len(polygon)
        if count < 3 or count > 8 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in polygon):
            raise ValueError('Desk polygon must have 3-8 finite vertices')
        area=sum(polygon[i][0]*polygon[(i+1)%count][1]-polygon[(i+1)%count][0]*polygon[i][1] for i in range(count))
        if abs(area)<1e-9: raise ValueError('Degenerate desk polygon')
        sign=1 if area>0 else -1
        for i,(x,y) in enumerate(polygon):
            bx,by=polygon[(i+1)%count]; cx,cy=polygon[(i+2)%count]
            dx,dy=bx-x,by-y; length=math.hypot(dx,dy)
            if length<1e-6 or sign*(dx*(cy-by)-dy*(cx-bx)) <= 1e-9:
                raise ValueError('Desk polygon must be strictly convex and perimeter ordered')
            nx,ny=sign*dy/length,-sign*dx/length
            yaw=math.atan2(-ny,-nx)
            if reference=='laser':
                offset_x=math.cos(yaw)*lx-math.sin(yaw)*ly
                offset_y=math.sin(yaw)*lx+math.cos(yaw)*ly
                px,py=(x+bx)/2+nx*gap-offset_x,(y+by)/2+ny*gap-offset_y
            else:
                px,py=(x+bx)/2+nx*(gap+front),(y+by)/2+ny*(gap+front)
            # The complete rectangle must stay outside this supporting table edge.
            # This also catches an accidentally too-small laser-to-table distance.
            clearance=min((px+math.cos(yaw)*fx-math.sin(yaw)*fy-(x+bx)/2)*nx+
                          (py+math.sin(yaw)*fx+math.cos(yaw)*fy-(y+by)/2)*ny
                          for fx,fy in footprint)
            if clearance<=0:
                raise ValueError('Inspection viewpoint puts the robot body inside the tabletop')
            points.append({'id':desk_id+'-E'+str(i+1),
                           'x':px, 'y':py, 'yaw':yaw})
    result={'frame_id':'map','scene_scale':1,'calibrated':True,
            'selection':'best_three','parking_distance_m':gap,'parking_reference':reference,'waypoints':points}
    # calibrated refers to user-supplied table/robot geometry, not camera coverage.
    load_desks(result)
    return result
