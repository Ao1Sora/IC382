import math
import pytest
from ic382_navigation.inspection import canonical_desk, load_desks, shortest_visit_order


def test_path_costs_change_order_when_a_wall_makes_the_nearest_point_expensive():
    points=[{'id':p} for p in 'ABC']
    costs={(a,b):1. for a in [None,'A','B','C'] for b in 'ABC' if a!=b}
    costs[(None,'A')]=50.;costs[(None,'B')]=2.;costs[(None,'C')]=4.
    order,length=shortest_visit_order(points,costs)
    assert order[0]['id']=='B' and length==4.


def test_directed_unreachable_edges_do_not_rule_out_an_alternative_order():
    points=[{'id':p} for p in 'ABC']
    costs={(None,'A'):1.,('A','B'):math.inf,('A','C'):2.,('C','B'):3.}
    order,length=shortest_visit_order(points,costs)
    assert [p['id'] for p in order]==['A','C','B'] and length==6.
    with pytest.raises(ValueError):shortest_visit_order(points,{(None,'A'):1.})


def test_route_is_open_and_includes_every_stop_once():
    points=[{'id':p} for p in 'ABC']
    costs={(a,b):2. for a in [None,'A','B','C'] for b in 'ABC' if a!=b}
    order,length=shortest_visit_order(points,costs)
    assert sorted(p['id'] for p in order)==list('ABC') and length==6.


def test_desk_aliases_and_three_pose_validation():
    assert canonical_desk('table_04')==canonical_desk('T4')=='T04'
    assert canonical_desk('4')=='T04'
    assert canonical_desk('table')=='T01'
    doc={'frame_id':'map','waypoints':[dict(id='T04-'+p,x=0.,y=0.,yaw=0.) for p in 'ABC']}
    assert len(load_desks(doc)['T04'])==3
    doc['waypoints'].pop()
    with pytest.raises(ValueError):load_desks(doc)
