import json
import math
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[4]


def synthetic_audit():
    samples=[];ex=ey=et=tx=ty=tt=0.
    def sample(state='MOVING',point=''):
        samples.append({'sample_wall':len(samples)*.1,'state':{'state':state,'point_id':point},
                        'estimated_map_xy':[ex,ey],'estimated_yaw':et,
                        'world_pose':[tx,ty,0.],'world_yaw':tt})
    sample()
    def move(distance=0.,turn=0.):
        nonlocal ex,ey,et,tx,ty,tt
        ex+=distance*math.cos(et);ey+=distance*math.sin(et);et+=turn
        tx+=distance*1.01*math.cos(tt);ty+=distance*1.01*math.sin(tt);tt+=turn*.97
        sample()
    move(distance=6.);move(turn=math.pi/2);move(distance=6.)
    sample('WAITING_FOR_WORK','T04-A')
    move(turn=math.pi/2);move(distance=8.)
    sample('WAITING_FOR_WORK','T04-C')
    move(turn=math.pi/2);move(distance=8.)
    sample('WAITING_FOR_WORK','T04-B')
    return {'result':{'success':True},'samples':samples}


def invoke(tmp_path,audit):
    source=tmp_path/'audit.json';result=tmp_path/'fit.json'
    source.write_text(json.dumps(audit))
    run=subprocess.run([sys.executable,str(REPO/'scripts/calibrate-wheel-odometry.py'),str(source),
                        '--output',str(result),'--anchor-x','0','--anchor-y','0'],capture_output=True,text=True)
    return run,result


def test_recovers_known_wheel_bias_and_predicts_a_held_out_checkpoint(tmp_path):
    run,path=invoke(tmp_path,synthetic_audit())
    assert run.returncode==0,run.stderr
    fit=json.loads(path.read_text())
    assert abs(fit['wheel_radius']-.63*1.01)<1e-8
    assert abs(fit['wheel_track']-3.49*1.01/.97)<1e-8
    holdout=fit['checkpoints']['T04-B']
    assert not holdout['used_for_fitting'] and holdout['position_error_scene']<1e-8


def test_rejects_a_truth_audit_that_missed_the_initial_motion(tmp_path):
    audit=synthetic_audit();audit['samples'][0]['sample_wall']=50.
    run,path=invoke(tmp_path,audit)
    assert run.returncode!=0 and '--odometry' in run.stderr
    assert not path.exists()
