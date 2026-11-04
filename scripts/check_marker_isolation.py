"""Regression: cached RViz markers must not leak across empty/new maps or SLAM."""
from pathlib import Path
from unittest.mock import Mock
import rclpy
from visualization_msgs.msg import Marker
from map_ui import desk_markers
from robot_console import Console

rclpy.init()
app=Console(Path(__file__).resolve().parents[1],test_mode=True)
visible={}
def consume(message):
    for marker in message.markers:
        if marker.action==Marker.DELETEALL: visible.clear()
        elif marker.action==Marker.ADD:visible[(marker.ns,marker.id)]=marker
try:
    stamp=app.node.get_clock().now().to_msg()
    desks=[dict(id='T01',polygon=[[0,0],[1,0],[1,1],[0,1]])]
    consume(desk_markers(desks,0,stamp));assert len(visible)==2
    consume(desk_markers([],0,stamp));assert visible=={}, 'Unannotated map retained old markers'
    consume(desk_markers(desks*3,0,stamp));assert len(visible)==6
    consume(desk_markers(desks,0,stamp));assert len(visible)==2, 'Removed desks retained cached IDs'
    app.config['inspection']['desks']=desks
    app.markers=Mock();app.markers.publish.side_effect=consume
    app.mode='SLAM';app.publish_desks();assert visible=={}, 'SLAM showed previous scene desks'
    assert app.config['inspection']['desks']==desks, 'Hiding should not erase the saved scene'
    app.mode='MANUAL';app.map_items=[];app.publish_desks();assert visible=={}
    app.map_items=None;app.publish_desks();assert len(visible)==2
    print('PASS: empty scene clears cache; fewer desks replace IDs; SLAM and map menu hide previous annotations')
finally:app.node.destroy_node();rclpy.shutdown()
