import math
import numpy as np
from ic382_navigation.local_scan_match import LocalScanMatcher, alignment_supports_navigation, propagate_pose


def scene():
    grid=np.zeros((200,200),dtype=np.int8)
    grid[60,:]=100;grid[140,:]=100;grid[:,40]=100;grid[:,160]=100
    matcher=LocalScanMatcher(grid,.05,(-5.,-5.,0.))
    x=np.linspace(-2.,2.,60)
    y=np.linspace(-1.5,1.5,50)
    points=np.vstack((np.column_stack((x,np.full(len(x),-1.975))),
        np.column_stack((x,np.full(len(x),2.025))),
        np.column_stack((np.full(len(y),-2.975),y)),
        np.column_stack((np.full(len(y),3.025),y))))
    return matcher,points


def test_small_error_improves_alignment_with_bounded_step():
    matcher,points=scene()
    result=matcher.match(points,[.025,-.015,math.radians(.75)])
    assert result['apply']
    assert result['after_score']>result['before_score']
    assert np.linalg.norm(result['correction'][:2])<=.060001
    assert abs(result['correction'][2])<=math.radians(4.00001)
    corrected=np.array([.025,-.015,math.radians(.75)])+result['correction']
    assert np.linalg.norm(corrected[:2])<np.linalg.norm([.025,-.015])


def test_aligned_scan_is_not_repeatedly_reset():
    matcher,points=scene()
    result=matcher.match(points,[0.,0.,0.])
    assert result['healthy'] and not result['apply']


def test_large_error_never_gets_global_correction():
    matcher,points=scene()
    result=matcher.match(points,[.4,.3,math.radians(15)])
    assert not result['apply'] and not result['healthy']
    assert np.linalg.norm(result['offset'][:2])<=.120001
    assert abs(result['offset'][2])<=math.radians(6.0001)


def test_single_wall_cannot_cause_arbitrary_along_wall_shift():
    matcher,_=scene()
    x=np.linspace(-1.,1.,80)
    result=matcher.match(np.column_stack((x,np.full(len(x),2.025))),[.04,0.,0.])
    assert not result['apply']
    assert np.linalg.norm(result['offset'][:2])<1e-8


def test_good_match_at_correction_boundary_does_not_falsely_cancel_navigation():
    assert alignment_supports_navigation(dict(healthy=True,boundary=True,before_score=.82))
    assert not alignment_supports_navigation(dict(healthy=False,boundary=True,before_score=.30))
    assert not alignment_supports_navigation(dict(healthy=True,boundary=True,before_score=.60))


def test_turn_error_outside_old_window_converges_without_global_search():
    matcher,world=scene()
    for angle in (math.radians(80),math.radians(-179)):
        c,s=math.cos(angle),math.sin(angle)
        points=world@np.array([[c,-s],[s,c]])
        estimate=np.array([.07,-.03,angle+math.radians(4)])
        for _ in range(5):
            result=matcher.match(points,estimate)
            if result['apply']:estimate+=result['correction']
        assert np.linalg.norm(estimate[:2])<.025
        assert abs(estimate[2]-angle)<math.radians(.5)


def test_scan_time_correction_retains_intervening_turn_and_translation():
    # 200 ms of real turning after the scan must not become a false yaw error.
    old=[1.,2.,math.radians(179)]
    new=[1.01,2.,math.radians(-179)]
    corrected=[4.,3.,math.radians(89)]
    result=propagate_pose(corrected,old,new,[0.,0.,.15],.1)
    assert np.allclose(result[:2],[4.,2.99])
    assert abs(result[2]-(math.radians(91)+.015))<1e-8


def test_stationary_compensation_does_not_change_correction():
    assert np.allclose(propagate_pose([1.,2.,.3],[0.,0.,0.],[0.,0.,0.],[0.,0.,0.],.1),[1.,2.,.3])


def test_enlarged_single_step_can_exceed_old_limits_but_stays_local():
    matcher,points=scene()
    result=matcher.match(points,[.095,-.035,math.radians(5.5)])
    assert result['apply'] and not result['boundary']
    assert .03<np.linalg.norm(result['correction'][:2])<=.060001
    assert math.radians(2)<abs(result['correction'][2])<=math.radians(4.00001)
