#!/usr/bin/env python3
"""Example MAIN PROGRAM: request one desk and acknowledge timed demo work.

The navigation server itself never fabricates inspection completion.
"""
import argparse
import json
from pathlib import Path
import time
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from ic382_interfaces.action import InspectDesk
from ic382_interfaces.srv import CompleteInspection


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--desk',default='T04')
    parser.add_argument('--work-seconds',type=float,default=3.)
    parser.add_argument('--timeout',type=float,default=900.)
    parser.add_argument('--cancel-after',type=float,default=0.)
    parser.add_argument('--output',default='desk-inspection-result.json')
    args=parser.parse_args()
    rclpy.init();node=Node('desk_inspection_demo_main')
    client=ActionClient(node,InspectDesk,'/ic382/inspect_desk')
    work=node.create_client(CompleteInspection,'/ic382/complete_inspection')
    report={'desk':args.desk,'work_is_timed_placeholder':True,'feedback':[],'acknowledgements':[],
            'samples':[],'nonzero_commands_while_waiting':0}
    latest={};waiting={};sent=set();command=[0.,0.];odom={};handle=[None];done=[None]
    start=time.monotonic();last_sample=[0.];last_state=[None]
    def feedback(message):
        f=message.feedback
        state={'task_id':f.task_id,'state':f.state,'point_id':f.point_id,'visit_order':list(f.visit_order),'completed_points':f.completed_points}
        latest.clear();latest.update(state)
        key=(f.state,f.point_id)
        if key!=last_state[0]:
            print('STATE',json.dumps(state),flush=True);report['feedback'].append({'wall':time.monotonic()-start,**state});last_state[0]=key
        if f.state=='WAITING_FOR_WORK':waiting.setdefault((f.task_id,f.point_id),time.monotonic())
    def result(future):
        response=future.result();r=response.result
        done[0]={'status':response.status,'success':r.success,'task_id':r.task_id,'message':r.message,
                 'visited_points':list(r.visited_points),'planned_path_length':r.planned_path_length}
    def accepted(future):
        handle[0]=future.result()
        if not handle[0].accepted:done[0]={'success':False,'message':'goal_rejected'}
        else:handle[0].get_result_async().add_done_callback(result)
    def velocity(msg):
        command[:]=[msg.linear.x,msg.angular.z]
        key=(latest.get('task_id'),latest.get('point_id'))
        if latest.get('state')=='WAITING_FOR_WORK' and time.monotonic()-waiting.get(key,time.monotonic())>.3 and max(map(abs,command))>.001:
            report['nonzero_commands_while_waiting']+=1
    def position(msg):
        p=msg.pose.pose.position;q=msg.pose.pose.orientation
        odom.update(x=p.x,y=p.y,qz=q.z,qw=q.w)
    node.create_subscription(Twist,'/cmd_vel',velocity,10)
    node.create_subscription(Odometry,'/odom',position,10)
    def tick():
        now=time.monotonic()
        if latest.get('state')=='WAITING_FOR_WORK':
            key=(latest['task_id'],latest['point_id'])
            if key not in sent and now-waiting[key]>=args.work_seconds and work.service_is_ready():
                request=CompleteInspection.Request();request.task_id=key[0];request.point_id=key[1];request.success=True
                sent.add(key)
                def acknowledged(future,k=key):
                    response=future.result();record={'task_id':k[0],'point_id':k[1],'accepted':response.accepted,'message':response.message}
                    report['acknowledgements'].append(record);print('DEMO_WORK_STUB',json.dumps(record),flush=True)
                work.call_async(request).add_done_callback(acknowledged)
        if now-last_sample[0]>=1:
            report['samples'].append({'wall':now-start,'state':dict(latest),'odom':dict(odom),'cmd_vel':list(command)})
            Path(args.output).write_text(json.dumps(report,indent=2));last_sample[0]=now
    node.create_timer(.1,tick)
    try:
        deadline=time.monotonic()+90
        while not client.server_is_ready() and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.2)
        if not client.server_is_ready():raise RuntimeError('Inspection server unavailable')
        goal=InspectDesk.Goal();goal.desk_id=args.desk
        client.send_goal_async(goal,feedback_callback=feedback).add_done_callback(accepted)
        canceled=False
        while done[0] is None and time.monotonic()-start<args.timeout:
            rclpy.spin_once(node,timeout_sec=.1)
            if args.cancel_after and not canceled and handle[0] and time.monotonic()-start>=args.cancel_after:
                handle[0].cancel_goal_async();canceled=True
        if done[0] is None and handle[0]:
            handle[0].cancel_goal_async();end=time.monotonic()+5
            while done[0] is None and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
        report['result']=done[0] or {'success':False,'message':'demo_timeout'}
        end=time.monotonic()+.5
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
        report['final_cmd_vel']=list(command)
        Path(args.output).write_text(json.dumps(report,indent=2));print('RESULT',json.dumps(report['result']),flush=True)
    finally:
        node.destroy_node();rclpy.shutdown()
    return 0 if report.get('result',{}).get('success') else 1


if __name__=='__main__':raise SystemExit(main())
