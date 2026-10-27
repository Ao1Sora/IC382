"""Pure route ordering and encoder dead reckoning, independent of ROS/Isaac."""
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
        if len(poses) != 3 or len({p['id'] for p in poses}) != 3:
            raise ValueError(desk + ' must have three distinct poses')
    if not desks:
        raise ValueError('No inspection poses')
    return desks


def shortest_visit_order(points, costs):
    """Exact open-route ordering for supplied directed Nav2 path lengths.

    Key (None, point_id) denotes a path from the current position. Unreachable
    edges have infinite cost. There is no implied return to the starting point.
    """
    best = None
    for order in itertools.permutations(points):
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


class WheelIntegrator:
    def __init__(self, radius, track, maximum_dt=.5, turn_track=None, turn_blend_speed=.5):
        turn_track = track if turn_track is None else turn_track
        if not all(math.isfinite(v) and v > 0 for v in (radius, track, maximum_dt, turn_track, turn_blend_speed)):
            raise ValueError('Wheel dimensions and maximum_dt must be positive')
        self.radius, self.track, self.maximum_dt = radius, track, maximum_dt
        self.turn_track, self.turn_blend_speed = turn_track, turn_blend_speed
        self.x = self.y = self.yaw = 0.
        self.previous = None

    def update(self, stamp, left, right):
        if not all(math.isfinite(v) for v in (stamp, left, right)):
            raise ValueError('Non-finite encoder sample')
        v = self.radius * (left + right) / 2
        # Static turns have different scrub from rolling curves in this scene.
        # Both tracks are offline calibration constants, not pose observations.
        rolling = min(1., abs(v) / self.turn_blend_speed)
        effective_track = self.turn_track + rolling * (self.track - self.turn_track)
        w = self.radius * (right - left) / effective_track
        if self.previous is not None:
            old_stamp, old_v, old_w = self.previous
            dt = stamp - old_stamp
            if dt <= 0:
                raise ValueError('Encoder clock must increase; restart localization after a simulation reset')
            if dt > self.maximum_dt:
                raise ValueError('Encoder gap exceeds integration limit; localization must be reinitialized')
            speed, omega = (v + old_v) / 2, (w + old_w) / 2
            end = self.yaw + omega * dt
            if abs(omega) < 1e-8:
                self.x += speed * dt * math.cos(self.yaw)
                self.y += speed * dt * math.sin(self.yaw)
            else:
                self.x += speed / omega * (math.sin(end) - math.sin(self.yaw))
                self.y -= speed / omega * (math.cos(end) - math.cos(self.yaw))
            self.yaw = math.atan2(math.sin(end), math.cos(end))
        self.previous = (stamp, v, w)
        return self.x, self.y, self.yaw, v, w
