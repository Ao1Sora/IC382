"""Desk overlays and map click selection for the robot's RViz console."""
import math
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray


def select_desk(desks, x, y):
    if not math.isfinite(x) or not math.isfinite(y): return None
    candidates = []
    for index, desk in enumerate(desks):
        polygon = desk['polygon']
        inside = False
        distance = math.inf
        for a, b in zip(polygon, polygon[1:]+polygon[:1]):
            ax, ay = a; bx, by = b
            if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
                inside = not inside
            dx, dy = bx-ax, by-ay
            t = max(0., min(1., ((x-ax)*dx+(y-ay)*dy)/max(dx*dx+dy*dy, 1e-12)))
            distance = min(distance, math.hypot(x-ax-t*dx, y-ay-t*dy))
        candidates.append((0. if inside else distance, index))
    distance, index = min(candidates, default=(math.inf, None))
    return index if distance <= .75 else None


def desk_markers(desks, selected, stamp):
    result = MarkerArray()
    # An empty MarkerArray does not erase RViz's cached markers. Every message
    # replaces the whole scene, including when the new scene has zero desks.
    clear = Marker()
    clear.header.frame_id = 'map'; clear.header.stamp = stamp
    clear.action = Marker.DELETEALL
    result.markers.append(clear)
    for index, desk in enumerate(desks):
        polygon = desk['polygon']
        line = Marker()
        line.header.frame_id = 'map'; line.header.stamp = stamp
        line.ns = 'desk_boundary'; line.id = index; line.type = Marker.LINE_STRIP
        line.pose.orientation.w = 1.; line.scale.x = .045
        line.color.r = 1. if index == selected else .1
        line.color.g = 1.; line.color.b = .1 if index == selected else 1.; line.color.a = 1.
        line.points = [Point(x=float(x), y=float(y), z=.08) for x,y in polygon+polygon[:1]]
        label = Marker()
        label.header = line.header; label.ns = 'desk_labels'; label.id = index
        label.type = Marker.TEXT_VIEW_FACING; label.pose.orientation.w = 1.
        label.pose.position.x = sum(p[0] for p in polygon)/len(polygon)
        label.pose.position.y = sum(p[1] for p in polygon)/len(polygon)
        label.pose.position.z = .3; label.scale.z = .25; label.color = line.color
        label.text = str(desk['id'])+(' [SELECTED]' if index == selected else '')
        result.markers.extend([line,label])
    return result
