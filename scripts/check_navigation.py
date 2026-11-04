#!/usr/bin/env python3
"""Serial ROS regressions in domain 138; never launches the physical chassis."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import yaml

ROOT=Path(__file__).resolve().parents[1]
SOFTWARE=('check_keyboard.py','check_console_tasks.py','check_point_navigation.py',
          'check_localization_assist.py','check_map_catalog.py','check_marker_isolation.py',
          'check_reset_scope.py','check_local_alignment.py','check_console_callback_load.py')
CONTROLLERS=('check_inplace_controller.py','check_controller_collision.py',
             'check_body_clearance_planner.py','check_retreat_recovery.py')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',choices=('unit','quick','full'),default='quick')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    target=args.output or Path.home()/'.local/state/ic382/test-results'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,ROS_DOMAIN_ID='138')
    env['PYTHONPATH']=str(ROOT/'scripts')+os.pathsep+env.get('PYTHONPATH','')
    rows=[]
    def run(name,command,extra=None):
        print('CHECK',name,flush=True);started=time.monotonic()
        with (target/(name+'.log')).open('w') as log:
            p=subprocess.run(command,cwd=ROOT,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT,timeout=150)
        rows.append(dict(name=name,returncode=p.returncode,seconds=round(time.monotonic()-started,2)))
        (target/'summary.json').write_text(json.dumps(dict(domain=138,physical_motion=False,checks=rows),indent=2))
        if p.returncode:
            print((target/(name+'.log')).read_text()[-4000:]);raise SystemExit(p.returncode)
        print('PASS',name,flush=True)
    # All checks sharing the test domain run serially, including their cleanup.
    with open('/tmp/ic382-test-domain-138.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        tests=ROOT/'ros2_ws/src/ic382_navigation/test'
        run('unit',[sys.executable,'-m','pytest','-q',str(tests),'--ignore='+str(tests/'test_simulation_profile.py')])
        if args.suite!='unit':
            for name in SOFTWARE:run(name,[sys.executable,str(ROOT/'scripts'/name)])
            with tempfile.TemporaryDirectory(prefix='ic382-inspection-api-') as folder:
                fixture=Path(folder)/'points.yaml'
                fixture.write_text(yaml.safe_dump(dict(frame_id='map',selection='best_three',waypoints=[
                    dict(id=desk+'-'+letter,x=float(i),y=0.,yaw=0.)
                    for desk,letters in [('T04','ABCD'),('T01','ABC')] for i,letter in enumerate(letters)])))
                run('inspection-api',[sys.executable,str(ROOT/'scripts/check-desk-api.py'),'--ros-args',
                    '-p','points:='+str(fixture),'-p','log_directory:='+folder+'/logs',
                    '-p','minimum_dwell_seconds:=0.1','-p','work_timeout_seconds:=20.0'])
        if args.suite=='full':
            for name in CONTROLLERS:
                run(name,[sys.executable,str(ROOT/'scripts'/name)],
                    {'TEST_ROTATION_OBSTACLE':'1'} if name=='check_inplace_controller.py' else None)
    print('RESULTS',target,flush=True)

if __name__=='__main__':main()
