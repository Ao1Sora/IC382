from copy import deepcopy
import pytest
from ic382_navigation.teacher_profile import teacher_profile, validate_physical_points


def baseline():
    costmap = {'plugins':['voxel_layer','inflation_layer'],
               'voxel_layer':{'plugin':'nav2_costmap_2d::VoxelLayer', 'combination_method':0}}
    return {'amcl':{'ros__parameters':{'scan_topic':'scan'}},
            'controller_server':{'ros__parameters':{'FollowPath':{'plugin':'vendor_controller'}}},
            'local_costmap':{'local_costmap':{'ros__parameters':deepcopy(costmap)}},
            'global_costmap':{'global_costmap':{'ros__parameters':deepcopy(costmap)}},
            'velocity_smoother':{'ros__parameters':{}}}


def test_vendor_plugins_preserved_and_tabletop_layer_added_without_mutation():
    original = baseline(); before = deepcopy(original)
    result = teacher_profile(original, .1, .3, True)
    assert original == before
    assert result['amcl'] == before['amcl']
    assert result['controller_server'] == before['controller_server']
    for name in ('local_costmap','global_costmap'):
        params = result[name][name]['ros__parameters']
        assert params['plugins'][0] == 'static_layer'
        assert params['static_layer']['map_topic'] == '/ic382/navigation_map'
        assert params['voxel_layer']['combination_method'] == 1
    assert result['velocity_smoother']['ros__parameters']['max_velocity'] == [.1,0.,.3]


@pytest.mark.parametrize('linear,angular', [(3.5,.3),(.1,1.),(0.,.3),(float('nan'),.3)])
def test_reject_simulation_or_invalid_limits(linear, angular):
    with pytest.raises(ValueError): teacher_profile(baseline(), linear, angular)


@pytest.mark.parametrize('scale,calibrated', [(10,True),(1,False),(None,True)])
def test_reject_unmeasured_or_simulation_points(scale, calibrated):
    with pytest.raises(ValueError):
        validate_physical_points({'scene_scale':scale,'calibrated':calibrated})


def test_accept_one_measured_desk_and_reject_incomplete_desk():
    data = {'frame_id':'map','scene_scale':1,'calibrated':True,
            'waypoints':[{'id':'T04-'+suffix,'x':0.,'y':float(i),'yaw':0.}
                         for i,suffix in enumerate('ABC')]}
    assert len(validate_physical_points(data)['T04']) == 3
    data['waypoints'].pop()
    with pytest.raises(ValueError): validate_physical_points(data)


def test_teacher_mppi_and_dwb_trajectory_limits_match_physical_gate():
    data = baseline()
    tracker = data['controller_server']['ros__parameters']['FollowPath']
    tracker.update(vx_max=.5, vx_min=-.4, wz_max=1., max_vel_x=.5,
                   min_vel_x=-.4, max_speed_xy=.5, max_vel_theta=1., min_speed_xy=.2)
    result = teacher_profile(data,.1,.3)['controller_server']['ros__parameters']['FollowPath']
    assert result['plugin'] == 'vendor_controller'
    assert result['vx_max'] == result['max_vel_x'] == result['max_speed_xy'] == .1
    assert result['vx_min'] == result['min_vel_x'] == -.1
    assert result['wz_max'] == result['max_vel_theta'] == .3


def test_saved_map_mode_removes_sensor_layers_from_both_costmaps_only():
    data=baseline()
    result=teacher_profile(data,.05,.15,True,False)
    for name in ('local_costmap','global_costmap'):
        assert result[name][name]['ros__parameters']['plugins']==['static_layer','inflation_layer']
    assert result['amcl']==data['amcl']
    assert data['local_costmap']['local_costmap']['ros__parameters']['plugins'][0]=='voxel_layer'


def test_disabling_inflation_preserves_static_occupancy_and_robot_outline():
    data=baseline()
    for name in ('local_costmap','global_costmap'):
        data[name][name]['ros__parameters']['footprint']='[[-.1,-.2],[.3,-.2],[.3,.2],[-.1,.2]]'
    result=teacher_profile(data,.05,.15,True,False,False)
    for name in ('local_costmap','global_costmap'):
        p=result[name][name]['ros__parameters']
        assert p['inflation_layer']['enabled'] is False
        assert p['static_layer']['map_topic']=='/ic382/navigation_map'
        assert p['footprint']==data[name][name]['ros__parameters']['footprint']
