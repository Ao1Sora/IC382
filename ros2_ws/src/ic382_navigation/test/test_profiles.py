from copy import deepcopy
from pathlib import Path
import pytest
import yaml
from ic382_navigation.profiles import build_profile

REPO = Path(__file__).resolve().parents[4]


def sources():
    teacher = yaml.safe_load((REPO/'teacher/ros2/config/custom_nav2_params.yaml').read_text())
    overrides = yaml.safe_load((REPO/
        'ros2_ws/src/ic382_navigation/config/nav2_team_overrides.yaml').read_text())
    return teacher, overrides


def test_course_baseline_survives_team_adaptations_without_mutation():
    teacher, overrides = sources()
    original = deepcopy(teacher)
    profile = build_profile(teacher, overrides)
    assert teacher == original
    assert profile['bt_navigator'] == teacher['bt_navigator']
    assert profile['controller_server']['ros__parameters']['FollowPath']['critics'] == (
        teacher['controller_server']['ros__parameters']['FollowPath']['critics'])
    assert profile['amcl']['ros__parameters']['update_min_a'] == 0.2
    assert not profile['amcl']['ros__parameters']['set_initial_pose']
    assert 'initial_pose' not in profile['amcl']['ros__parameters']
    assert profile['planner_server']['ros__parameters']['GridBased']['allow_unknown'] is False


@pytest.mark.parametrize('field,value', [('min_speed_xy', 0.0), ('min_speed_theta', 0.5),
                                       ('xy_goal_tolerance', 2.0)])
def test_inconsistent_motion_profile_is_rejected(field, value):
    teacher, overrides = sources()
    overrides['controller_server']['ros__parameters']['FollowPath'][field] = value
    with pytest.raises(ValueError):
        build_profile(teacher, overrides)


def test_laser_clearing_cannot_exceed_usable_laser_range():
    teacher, overrides = sources()
    overrides['local_costmap']['local_costmap']['ros__parameters'][
        'obstacle_layer']['scan']['raytrace_max_range'] = 300.0
    with pytest.raises(ValueError, match='ranges'):
        build_profile(teacher, overrides)


def test_initial_pose_applies_only_to_this_generated_instance():
    teacher, overrides = sources()
    pose = dict(x=-270.0, y=35.0, z=0.0, yaw=0.2)
    runtime = build_profile(teacher, overrides, pose)
    assert runtime['amcl']['ros__parameters']['initial_pose'] == pose
    assert runtime['amcl']['ros__parameters']['set_initial_pose']
    assert 'initial_pose' not in build_profile(teacher, overrides)['amcl']['ros__parameters']
    with pytest.raises(ValueError):
        build_profile(teacher, overrides, {**pose, 'yaw': float('nan')})
