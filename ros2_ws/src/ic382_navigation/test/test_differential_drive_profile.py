from copy import deepcopy
import json
import math
from ic382_navigation.teacher_profile import differential_drive_profile, differential_clearance_profile


def test_turn_in_place_profile_removes_car_curvature_constraints_and_keeps_collision_checks():
    source={'controller_server':{'ros__parameters':{'FollowPath':{'plugin':'mppi'}}},
            'planner_server':{'ros__parameters':{'GridBased':{'motion_model_for_search':'DUBIN'}}},
            'local_costmap':{'footprint':'unchanged'}}
    before=deepcopy(source)
    profile=differential_drive_profile(source,.05,.15,lattice_filepath="diff.json")
    assert source==before and profile['local_costmap']==source['local_costmap']
    c=profile['controller_server']['ros__parameters'];p=profile['planner_server']['ros__parameters']['GridBased']
    assert 'ClearanceLattice' in p['plugin'] and 'motion_model_for_search' not in p
    assert p['smooth_path'] is False
    assert p['lattice_filepath']=='diff.json'
    assert c['goal_checker']['xy_goal_tolerance']==.1
    assert c['goal_checker']['stateful'] is True
    assert c['goal_checker']['yaw_goal_tolerance']==.15
    assert c['FollowPath']['plugin']=='ic382_planners/StagedGoalController'
    assert c['FollowPath']['use_rotate_to_heading'] is False
    assert p['planning_clearance']==.1
    assert profile['planner_server']['ros__parameters']['GridBasedWide']['planning_clearance']==.1
    assert c['FollowPath']['use_collision_detection']
    assert c['FollowPath']['max_allowed_time_to_collision_up_to_carrot']>.05/.02
    assert c['FollowPath']['lookahead_dist']<=.15
    assert c['FollowPath']['regulated_linear_scaling_min_radius']>=.05/.15
    assert c['FollowPath']['rotate_to_heading_angular_vel']==.15
    assert c['FollowPath']['desired_linear_vel']==.05
    assert c['FollowPath']['min_approach_linear_velocity']<=.05
    assert c['progress_checker']['required_movement_radius']<.05
    assert c['progress_checker']['movement_time_allowance']>3.1416/.15
    assert c['FollowPath']['max_angular_accel']/20>=.15
    assert profile['behavior_server']['ros__parameters']['global_frame']=='map'
    assert profile['behavior_server']['ros__parameters']['max_rotational_vel']==.15


def test_full_polygon_is_used_without_inflation_or_extra_padding():
    body=[[-.24,-.2],[-.24,.2],[.16,.2],[.16,-.2]]
    params=dict(footprint=json.dumps(body),resolution=.05,plugins=['static_layer','inflation_layer'],
                inflation_layer=dict(enabled=True,inflation_radius=.3))
    source={name:{name:{'ros__parameters':deepcopy(params)}} for name in ('local_costmap','global_costmap')}
    result=differential_clearance_profile(source)
    assert source['local_costmap']['local_costmap']['ros__parameters']==params
    for name in ('local_costmap','global_costmap'):
        costmap=result[name][name]['ros__parameters']
        assert costmap['footprint']==params['footprint']
        assert costmap['footprint_padding']==0
        assert 'inflation_layer' not in costmap['plugins']
        assert costmap['inflation_layer']['enabled'] is False
