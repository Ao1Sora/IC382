import math
import pytest
from ic382_navigation.runtime_config import generate_candidates, resolve_runtime
from ic382_navigation.inspection import shortest_visit_order

FOOTPRINT=[[-.2,-.2],[.35,-.2],[.35,.2],[-.2,.2]]


def settings(polygon=None):
    return {'desks':[{'id':'T04','polygon':polygon or [[0.,0.],[2.,0.],[2.,1.],[0.,1.]]}]}


@pytest.mark.parametrize('clockwise',[False,True])
def test_half_metre_clearance_uses_robot_front_and_faces_desk(clockwise):
    config=settings()
    if clockwise:config['desks'][0]['polygon'].reverse()
    result=generate_candidates(config, FOOTPRINT)
    assert len(result['waypoints'])==4
    for p in result['waypoints']:
        # Robot-front midpoint is precisely 0.5m outside one of the table edges.
        front=(p['x']+.35*math.cos(p['yaw']),p['y']+.35*math.sin(p['yaw']))
        assert min(abs(front[0]),abs(front[0]-2),abs(front[1]),abs(front[1]-1))==pytest.approx(.5)
        assert math.cos(p['yaw'])*(1-p['x'])+math.sin(p['yaw'])*(.5-p['y'])>0


def test_custom_gap_and_invalid_geometry():
    config=settings();config['parking_distance_m']=.8
    assert generate_candidates(config,FOOTPRINT)['waypoints'][0]['y']==pytest.approx(-1.15)
    config['parking_distance_m']=-.1
    with pytest.raises(ValueError):generate_candidates(config,FOOTPRINT)
    with pytest.raises(ValueError):generate_candidates(settings([[0,0],[1,1],[0,1],[1,0]]),FOOTPRINT)


def test_best_three_uses_obstacle_aware_path_cost_not_four_stop_route():
    points=[{'id':x} for x in 'ABCD']
    costs={(a,b):1. for a in [None,'A','B','C','D'] for b in 'ABCD' if a!=b}
    for key in costs:
        if 'A' in key:costs[key]=math.inf
    order,length=shortest_visit_order(points,costs,3)
    assert {p['id'] for p in order}==set('BCD') and length==3.


def test_relative_paths_resolve_from_config_and_boolean_is_validated(tmp_path):
    result=resolve_runtime({'schema_version':1,'map':'maps/test.yaml','start_hardware':False},tmp_path/'runtime.yaml')
    assert result['map']==str(tmp_path/'maps/test.yaml')
    with pytest.raises(ValueError):resolve_runtime({'schema_version':1,'start_hardware':'false'},tmp_path/'runtime.yaml')
