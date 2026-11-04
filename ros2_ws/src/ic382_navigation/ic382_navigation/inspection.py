"""Desk identity, candidate validation and obstacle-aware visit ordering."""
import itertools
import math


def canonical_desk(value):
    key = str(value).strip().upper()
    if key == 'TABLE':
        return 'T01'
    if key.isdigit():
        return 'T%02d' % int(key)
    if key.startswith('TABLE_'):
        key = 'T' + key[6:]
    if key.startswith('T') and key[1:].isdigit():
        key = 'T%02d' % int(key[1:])
    return key


def load_desks(document):
    if document.get('frame_id') != 'map':
        raise ValueError('Inspection poses must use map frame')
    desks = {}
    points = document.get('waypoints', [])
    if not isinstance(points, list):raise ValueError('Inspection poses must be a list')
    for point in points:
        if not isinstance(point, dict) or not isinstance(point.get('id'), str):
            raise ValueError('Inspection point needs a string id')
        if not all(isinstance(point.get(k), (float, int)) and not isinstance(point[k], bool)
                   and math.isfinite(point[k]) for k in ('x', 'y', 'yaw')):
            raise ValueError('Invalid inspection pose')
        desk = canonical_desk(point['id'].split('-')[0])
        if desk not in ('T01', 'T02', 'T03', 'T04'):
            raise ValueError('Unknown mission desk: ' + desk)
        desks.setdefault(desk, []).append(dict(point))
    for desk, poses in desks.items():
        expected = len(poses) if document.get('selection') == 'best_three' else 3
        if not 3 <= expected <= 8 or len(poses) != expected or len({p['id'] for p in poses}) != expected:
            raise ValueError(desk + ' must have three distinct poses')
    if not desks:
        raise ValueError('No inspection poses')
    return desks


def shortest_visit_order(points, costs, count=None):
    """Exact open-route ordering for supplied directed Nav2 path lengths.

    Key (None, point_id) denotes a path from the current position. Unreachable
    edges have infinite cost. There is no implied return to the starting point.
    """
    best = None
    for order in itertools.permutations(points, len(points) if count is None else count):
        previous, length = None, 0.
        for point in order:
            edge = costs.get((previous, point['id']), math.inf)
            if not math.isfinite(edge) or edge < 0:
                length = math.inf
                break
            length += edge
            previous = point['id']
        if math.isfinite(length) and (best is None or length < best[1]):
            best = (list(order), length)
    if best is None:
        raise ValueError('No obstacle-aware route visits all remaining inspection points')
    return best


def next_inspection_point(points, current):
    """Select just the next stop from the current pose; never predict later legs."""
    if not points:raise ValueError('No remaining inspection points')
    return min(points,key=lambda p:(math.hypot(p['x']-current['x'],p['y']-current['y']),p['id']))
