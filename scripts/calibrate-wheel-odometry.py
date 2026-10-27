#!/usr/bin/env python3
"""OFFLINE ONLY: fit wheel constants from a completed diagnostic audit.

Truth in this file is used to calibrate constants, never fed into a ROS node.
Hold one completed checkpoint out of fitting to expose overfitting.
"""
import argparse
import json
import math
from pathlib import Path


def angle(value):return math.atan2(math.sin(value),math.cos(value))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('audit')
    parser.add_argument('--output',required=True)
    parser.add_argument('--odometry',help='Full demo result, required when the truth audit started after motion')
    parser.add_argument('--holdout',default='T04-B')
    parser.add_argument('--radius',type=float,default=.63)
    parser.add_argument('--track',type=float,default=3.49)
    parser.add_argument('--anchor-x',type=float,default=-278.8637905602745)
    parser.add_argument('--anchor-y',type=float,default=32.96996906027461)
    args=parser.parse_args()
    audit=json.loads(Path(args.audit).read_text())
    if not (audit.get('result') or {}).get('success'):raise ValueError('Audit must contain a completed run')
    samples=audit['samples']
    if args.odometry:
        truth={}
        for row in samples:
            if row['state']['state']=='WAITING_FOR_WORK':truth[row['state']['point_id']]=row
        samples=[]
        for row in json.loads(Path(args.odometry).read_text())['samples']:
            odom=row.get('odom',{})
            if not all(k in odom for k in ('x','y','qz','qw')):continue
            samples.append({'sample_wall':row['wall'],'state':{'state':'ODOMETRY_ONLY'},
                            'estimated_map_xy':[args.anchor_x+odom['x'],args.anchor_y+odom['y']],
                            'estimated_yaw':2*math.atan2(odom['qz'],odom['qw'])})
        for point,row in truth.items():
            index=min(range(len(samples)),key=lambda i:abs(samples[i]['sample_wall']-row['sample_wall']))
            if abs(samples[index]['sample_wall']-row['sample_wall'])>.1:raise ValueError('Checkpoint timestamps do not match')
            samples[index].update(state=row['state'],world_pose=row['world_pose'],world_yaw=row['world_yaw'])
    elif samples[0]['sample_wall']>1:
        raise ValueError('Truth audit missed initial motion; supply --odometry to avoid an invalid arc reconstruction')
    segments=[];stops={};x,y=args.anchor_x,args.anchor_y;yaw=0.
    for index,sample in enumerate(samples):
        px,py=sample['estimated_map_xy'];raw=sample['estimated_yaw']
        delta=angle(raw-yaw);mid=yaw+delta/2
        distance=(px-x)*math.cos(mid)+(py-y)*math.sin(mid)
        if abs(delta)>1e-8:distance*=delta/(2*math.sin(delta/2))
        segments.append((distance,yaw,delta));x,y,yaw=px,py,yaw+delta
        if sample['state']['state']=='WAITING_FOR_WORK':stops[sample['state']['point_id']]=index
    train={p:i for p,i in stops.items() if p!=args.holdout}
    if len(train)<2 or args.holdout not in stops:raise ValueError('Need two training stops and a separate holdout')
    best=None
    for step in range(1501):
        gain=.9+step*.0001;px=py=0.;predictions={}
        for index,(distance,start,delta) in enumerate(segments):
            scaled=delta*gain
            chord=distance if abs(scaled)<1e-8 else distance*2*math.sin(scaled/2)/scaled
            px+=chord*math.cos((start+delta/2)*gain)
            py+=chord*math.sin((start+delta/2)*gain)
            if index in stops.values():predictions[index]=(px,py,(start+delta)*gain)
        numerator=denominator=0.
        for index in train.values():
            vx,vy,_=predictions[index];tx,ty=samples[index]['world_pose'][:2]
            numerator+=vx*(tx-args.anchor_x)+vy*(ty-args.anchor_y);denominator+=vx*vx+vy*vy
        scale=numerator/denominator
        if not .95<scale<1.05:continue
        score=0.
        for index in train.values():
            vx,vy,heading=predictions[index];tx,ty=samples[index]['world_pose'][:2]
            score+=(args.anchor_x+vx*scale-tx)**2+(args.anchor_y+vy*scale-ty)**2
            score+=(3.49*angle(heading-samples[index]['world_yaw']))**2
        if best is None or score<best[0]:best=(score,gain,scale,predictions)
    if best is None:raise ValueError('No bounded calibration fit')
    score,gain,scale,predictions=best;checks={}
    for point,index in stops.items():
        vx,vy,heading=predictions[index];sample=samples[index];tx,ty=sample['world_pose'][:2]
        checks[point]={'used_for_fitting':point!=args.holdout,
                      'position_error_scene':math.hypot(args.anchor_x+vx*scale-tx,args.anchor_y+vy*scale-ty),
                      'yaw_error_rad':angle(heading-sample['world_yaw'])}
    report={'offline_only':True,'source_audit':str(Path(args.audit)),
            'wheel_radius':args.radius*scale,'wheel_track':args.track*scale/gain,
            'distance_gain':scale,'angular_gain':gain,'training_score':score,'checkpoints':checks}
    Path(args.output).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
