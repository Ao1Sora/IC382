from pathlib import Path
import math
import json
import pytest
import yaml
from ic382_navigation.simulation_profile import prepare_simulation


def test_isaac_scale_gap_static_layers_and_footprint():
    sim = Path(__file__).resolve().parents[4]/'simulation/config'
    config = yaml.safe_load((sim/'runtime.yaml').read_text())
    baseline = yaml.safe_load((sim/'teacher_nav2.yaml').read_text())
    overrides = yaml.safe_load((sim/'course_overrides.yaml').read_text())
    profile, points = prepare_simulation(baseline, overrides, config)
    assert len(points['waypoints']) == 4 * len(config['inspection']['desks'])
    assert points['selection'] == 'best_three'
    first = points['waypoints'][0]
    a, b = config['inspection']['desks'][0]['polygon'][:2]
    front_x = first['x'] + 5.05 * math.cos(first['yaw'])
    front_y = first['y'] + 5.05 * math.sin(first['yaw'])
    distance = abs((b[0]-a[0])*(front_y-a[1]) - (b[1]-a[1])*(front_x-a[0])) / math.dist(a, b)
    assert distance == pytest.approx(5.)
    for name in ('global_costmap','local_costmap'):
        costmap = profile[name][name]['ros__parameters']
        assert costmap['plugins'] == ['static_layer','inflation_layer']
        assert costmap['inflation_layer']['enabled'] is False
        assert json.loads(costmap['footprint']) == config['robot_footprint_scene']
    assert profile['controller_server']['ros__parameters']['FollowPath']['max_vel_x'] == 2.
    config['use_sim_time'] = False
    with pytest.raises(ValueError): prepare_simulation(baseline, overrides, config)
