import itertools
import math
import pytest
from ic382_navigation.inspection import WheelIntegrator, canonical_desk, load_desks, shortest_visit_order


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


def test_straight_encoder_odometry_and_stationary_input():
    odom=WheelIntegrator(.5,1.)
    odom.update(0.,2.,2.)
    for i in range(1,11):odom.update(i/10.,2.,2.)
    assert odom.x==pytest.approx(1.) and odom.y==0 and odom.yaw==0
    still=WheelIntegrator(.5,1.);still.update(0.,0.,0.);still.update(.1,0.,0.)
    assert (still.x,still.y,still.yaw)==(0.,0.,0.)


def test_opposite_encoders_turn_without_translating():
    odom=WheelIntegrator(.5,1.);odom.update(0.,-1.,1.)
    odom.update(.5,-1.,1.)
    assert odom.x==0 and odom.y==0 and odom.yaw==pytest.approx(.5)


def test_offline_scrub_calibration_applies_to_stationary_turns_not_rolling_curves():
    turn=WheelIntegrator(.5,1.,turn_track=2.,turn_blend_speed=.5)
    assert turn.update(0.,-1.,1.)[4]==pytest.approx(.5)
    rolling=WheelIntegrator(.5,1.,turn_track=2.,turn_blend_speed=.5)
    assert rolling.update(0.,1.,3.)[4]==pytest.approx(1.)


def test_angle_encoders_preserve_distance_through_wrap_and_stop():
    odom=WheelIntegrator(.5,1.)
    odom.update_positions(0.,math.pi-.1,math.pi-.1)
    odom.update_positions(.2,-math.pi+.1,-math.pi+.1)
    assert odom.x==pytest.approx(.1) and odom.y==0
    assert odom.update_positions(.3,-math.pi+.1,-math.pi+.1)[3:]==(0.,0.)


def test_angle_encoders_integrate_a_known_arc_and_reject_mode_or_clock_changes():
    odom=WheelIntegrator(.5,1.);odom.update_positions(0.,0.,0.)
    odom.update_positions(.5,0.,1.)
    assert odom.x==pytest.approx(.5*math.sin(.5))
    assert odom.y==pytest.approx(.5*(1-math.cos(.5)))
    assert odom.yaw==pytest.approx(.5)
    with pytest.raises(ValueError):odom.update(.6,0.,0.)
    with pytest.raises(ValueError):odom.update_positions(.5,0.,1.)
    with pytest.raises(ValueError):odom.update_positions(2.,0.,1.)


def test_encoder_arc_and_clock_faults():
    odom=WheelIntegrator(1.,2.);odom.update(0.,0.,2.)
    odom.update(.5,0.,2.)
    assert odom.x==pytest.approx(math.sin(.5))
    assert odom.y==pytest.approx(1-math.cos(.5))
    with pytest.raises(ValueError):odom.update(.5,0.,2.)
    with pytest.raises(ValueError):odom.update(2.,0.,2.)
    with pytest.raises(ValueError):odom.update(.6,math.nan,2.)


def test_desk_aliases_and_three_pose_validation():
    assert canonical_desk('table_04')==canonical_desk('T4')=='T04'
    assert canonical_desk('4')=='T04'
    assert canonical_desk('table')=='T01'
    doc={'frame_id':'map','waypoints':[dict(id='T04-'+p,x=0.,y=0.,yaw=0.) for p in 'ABC']}
    assert len(load_desks(doc)['T04'])==3
    doc['waypoints'].pop()
    with pytest.raises(ValueError):load_desks(doc)
