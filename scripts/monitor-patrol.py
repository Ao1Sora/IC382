#!/usr/bin/env python3
"""Monitor actual ROS mission plus independent simulator ground truth for evidence."""
import argparse
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped

p = argparse.ArgumentParser()
p.add_argument('--timeout', type=float, default=1800.)
p.add_argument('--output', required=True)
p.add_argument('--start', action='store_true')
p.add_argument('--first-desk', default='')
p.add_argument('--expected-arrivals', type=int, default=1)
args = p.parse_args()
rclpy.init()
n = Node('patrol_evidence_monitor')
data = {'purpose': 'Isaac simulation evidence; no physical robot tested',
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'samples': [], 'arrivals': [], 'dwell_nonzero_commands': 0}
state, goals = {}, {}
start = time.monotonic()
state_since = start
cmd = [0., 0.]
amcl = {}
last_sample = start
service_called = False
last_start_attempt = 0.0
bound_run_id = None
start_client = n.create_client(Trigger, '/ic382/start_mission')
cancel_client = n.create_client(Trigger, '/ic382/cancel_mission')


def status(msg):
    global state, state_since, bound_run_id
    update = json.loads(msg.data)
    if bound_run_id is None:
        if update.get('state') != 'IDLE':
            return
        if args.first_desk and update.get('desk_id') != args.first_desk:
            return
        bound_run_id = update['run_id']
    if update.get('run_id') != bound_run_id:
        return
    if update.get('state') != state.get('state'):
        state_since = time.monotonic()
        print('STATE', json.dumps(update), flush=True)
    state = update


def event(msg):
    record = json.loads(msg.data)
    if record.get('run_id') != bound_run_id:
        return
    details = record.get('data', {})
    if record['event'] == 'navigation_requested':
        goals[details['desk_id']] = details['goal']
    if record['event'] == 'navigation_succeeded':
        live = json.loads(Path('/workspace/logs/course601-live.json').read_text())
        goal = goals[details['desk_id']]
        true_xy = live['world_pose'][:2]
        data['arrivals'].append({
            'desk_id': details['desk_id'], 'round': details['round'], 'goal': goal,
            'world_xy': true_xy, 'amcl': dict(amcl),
            'true_position_error_scene': math.hypot(true_xy[0]-goal['x'], true_xy[1]-goal['y'])})


def command(msg):
    cmd[:] = [msg.linear.x, msg.angular.z]
    if (state.get('state') in ('INSPECTING', 'TAGGING')
            and time.monotonic()-state_since > .3 and max(map(abs, cmd)) > .001):
        data['dwell_nonzero_commands'] += 1


def pose(msg):
    pos, q = msg.pose.pose.position, msg.pose.pose.orientation
    amcl.update(x=pos.x, y=pos.y,
                yaw=math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)),
                variance_x=msg.pose.covariance[0], variance_y=msg.pose.covariance[7])


n.create_subscription(String, '/ic382/mission_status', status, 10)
n.create_subscription(String, '/ic382/events', event, 100)
n.create_subscription(Twist, '/cmd_vel', command, 10)
n.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', pose, 10)


def start_response(future):
    global service_called
    response = future.result()
    service_called = response.success
    print('START', response, flush=True)


try:
    while rclpy.ok() and time.monotonic()-start < args.timeout:
        rclpy.spin_once(n, timeout_sec=.1)
        now = time.monotonic()
        if (args.start and not service_called and state.get('state') == 'IDLE'
                and not state.get('health') and now-last_start_attempt > 2.0):
            if start_client.service_is_ready():
                service_called = True
                last_start_attempt = now
                future = start_client.call_async(Trigger.Request())
                future.add_done_callback(start_response)
        if now-last_sample >= 2.:
            live = json.loads(Path('/workspace/logs/course601-live.json').read_text())
            sample = {'wall_elapsed': now-start, 'state': state.get('state'),
                      'world_xy': live['world_pose'][:2], 'cmd_vel': list(cmd), 'amcl': dict(amcl)}
            data['samples'].append(sample)
            last_sample = now
            if len(data['samples']) % 10 == 0:
                print('PROGRESS', json.dumps(sample), flush=True)
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, indent=2))
        if state.get('journal_confirmed'):
            if state.get('state') in ('FAILED', 'CANCELED'):
                break
            if state.get('state') == 'COMPLETED' and len(data['arrivals']) >= args.expected_arrivals:
                break
    data['final_status'] = state
    data['elapsed_wall_seconds'] = time.monotonic()-start
    data['expected_arrivals'] = args.expected_arrivals
    data['completed_and_logged'] = (state.get('state') == 'COMPLETED'
        and state.get('journal_confirmed', False) and len(data['arrivals']) >= args.expected_arrivals)
    if not data['completed_and_logged'] and service_called and cancel_client.service_is_ready():
        future = cancel_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(n, future, timeout_sec=3.)
    end = time.monotonic()+1.
    while time.monotonic() < end:
        rclpy.spin_once(n, timeout_sec=.1)
    data['final_cmd_vel'] = list(cmd)
    Path(args.output).write_text(json.dumps(data, indent=2))
    print('PATROL_RESULT', json.dumps({k:v for k,v in data.items() if k != 'samples'}), flush=True)
finally:
    n.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
raise SystemExit(0 if data['completed_and_logged'] else 1)
