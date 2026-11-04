#!/usr/bin/env python3
"""Estimate current scan-to-original-map alignment; --apply requires stationary idle robot."""
import argparse
import json
import math
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, map_coordinates
import rclpy
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from tf2_ros import Buffer, TransformListener
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from action_msgs.msg import GoalStatusArray


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.apply:
        raise RuntimeError('Read-only diagnostic: live refinement is handled by the bounded local_alignment node')
    import yaml
    root=Path(__file__).resolve().parents[1]
    config=yaml.safe_load((root/'ros2_ws/src/ic382_navigation/config/physical_runtime.yaml').read_text())
    map_file=Path(config['map'])
    meta=yaml.safe_load(map_file.read_text())
    original=Image.open(map_file.parent/meta['image']).convert('L')
    pixels=np.asarray(original)
    probability=pixels/255. if meta.get('negate',0) else 1-pixels/255.
    occupied=probability>meta['occupied_thresh']
    known=occupied | (probability<meta['free_thresh'])
    resolution=float(meta['resolution'])
    field=distance_transform_edt(~occupied)*resolution
    ox,oy,origin_yaw=meta['origin']
    assert abs(origin_yaw)<1e-8,'Rotated map origin requires explicit conversion'
    rclpy.init()
    node=rclpy.create_node('ic382_scan_alignment_assessment')
    buffer=Buffer();listener=TransformListener(buffer,node)
    state={};refs=[]
    for topic,kind,key in [('/scan',LaserScan,'scan'),('/odom_combined',Odometry,'odom'),('/cmd_vel',Twist,'command')]:
        refs.append(node.create_subscription(kind,topic,lambda msg,key=key:state.update({key:msg,key+'_at':time.monotonic()}),qos_profile_sensor_data))
    refs.append(node.create_subscription(GoalStatusArray,'/navigate_to_pose/_action/status',
        lambda msg:state.update(status=msg),QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL)))
    publisher=node.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
    end=time.monotonic()+8
    transform=None
    while time.monotonic()<end:
        rclpy.spin_once(node,timeout_sec=.05)
        if 'scan' in state:
            scan=state['scan']
            try:
                transform=buffer.lookup_transform('map',scan.header.frame_id,rclpy.time.Time.from_msg(scan.header.stamp))
                extrinsic=buffer.lookup_transform('base_footprint',scan.header.frame_id,rclpy.time.Time())
            except Exception:
                continue
            if time.monotonic()>end-3:break
    assert transform is not None,'No timestamped map-to-laser transform'
    scan=state['scan']
    base=np.array([transform.transform.translation.x,transform.transform.translation.y,yaw(transform.transform.rotation)])
    ranges=np.asarray(scan.ranges)
    angles=scan.angle_min+np.arange(len(ranges))*scan.angle_increment
    valid=np.isfinite(ranges)&(ranges>max(scan.range_min,.35))&(ranges<min(scan.range_max,5.))
    points=np.column_stack((ranges[valid]*np.cos(angles[valid]),ranges[valid]*np.sin(angles[valid])))
    points=points[::max(1,int(math.ceil(len(points)/300)))]
    assert len(points)>=40,'Insufficient useful scan endpoints'

    def distances(poses):
        poses=np.asarray(poses).reshape(-1,3)
        c=np.cos(poses[:,2,None]);s=np.sin(poses[:,2,None])
        x=poses[:,0,None]+c*points[None,:,0]-s*points[None,:,1]
        y=poses[:,1,None]+s*points[None,:,0]+c*points[None,:,1]
        col=(x-ox)/resolution-.5
        row=original.height-1-((y-oy)/resolution-.5)
        values=map_coordinates(field,[row.ravel(),col.ravel()],order=1,mode='constant',cval=2.).reshape(x.shape)
        valid_known=map_coordinates(known.astype(float),[row.ravel(),col.ravel()],order=0,mode='constant',cval=0.).reshape(x.shape)
        values[valid_known<.5]=2.
        return values

    def search(centre,xy_step,xy_span,yaw_step,yaw_span):
        offset=np.arange(-xy_span,xy_span+xy_step*.5,xy_step)
        dx,dy=np.meshgrid(offset,offset)
        all_poses=[];all_scores=[]
        for angle in np.arange(-yaw_span,yaw_span+yaw_step*.5,yaw_step):
            candidates=np.column_stack((centre[0]+dx.ravel(),centre[1]+dy.ravel(),np.full(dx.size,centre[2]+angle)))
            d=distances(candidates)
            score=np.mean(np.exp(-.5*(d/.08)**2),axis=1)
            all_poses.append(candidates);all_scores.append(score)
        poses=np.vstack(all_poses);scores=np.concatenate(all_scores)
        best=int(np.argmax(scores))
        return poses[best],float(scores[best]),poses,scores

    initial=distances([base])[0]
    coarse,_,candidates,scores=search(base,.05,.6,math.radians(2),math.radians(20))
    best,score,_,_=search(coarse,.01,.06,math.radians(.25),math.radians(2))
    after=distances([best])[0]
    before_score=float(np.mean(np.exp(-.5*(initial/.08)**2)))
    separated=(np.linalg.norm(candidates[:,:2]-best[:2],axis=1)>.15)|(np.abs(candidates[:,2]-best[2])>math.radians(5))
    competitor=float(np.max(scores[separated])) if np.any(separated) else 0.
    delta=best-base
    report=dict(map=str(map_file),points=len(points),before_laser_pose=base.tolist(),after_laser_pose=best.tolist(),
        correction_xy_m=delta[:2].tolist(),correction_yaw_deg=float(math.degrees(delta[2])),
        before_score=before_score,after_score=score,alternative_score=competitor,
        before_inlier_fraction=float(np.mean(initial<.1)),after_inlier_fraction=float(np.mean(after<.1)),
        before_median_distance_m=float(np.median(initial)),after_median_distance_m=float(np.median(after)),applied=False)
    report['confident']=bool(score>.45 and score-before_score>.025 and score-competitor>.01)
    folder=Path.home()/'.local/state/ic382/alignment'/time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(folder/'snapshot.npz',scan_points=points,map_pixels=pixels,base=base,best=best,resolution=resolution,origin=np.asarray(meta['origin']))
    # Engineering overlay: identical map crop, old scan red and matched scan green.
    world=[]
    for pose in (base,best):
        c,s=math.cos(pose[2]),math.sin(pose[2])
        world.append(points@np.array([[c,s],[-s,c]])+pose[:2])
    all_points=np.vstack(world)
    x0=max(0,int((np.min(all_points[:,0])-ox-.5)/resolution));x1=min(original.width,int((np.max(all_points[:,0])-ox+.5)/resolution))
    y0=max(0,int(original.height-(np.max(all_points[:,1])-oy+.5)/resolution));y1=min(original.height,int(original.height-(np.min(all_points[:,1])-oy-.5)/resolution))
    scale=3;crop=original.crop((x0,y0,x1,y1)).convert('RGB').resize(((x1-x0)*scale,(y1-y0)*scale))
    canvas=Image.new('RGB',(crop.width*2,crop.height+35),'white');draw=ImageDraw.Draw(canvas)
    for i,cloud in enumerate(world):
        canvas.paste(crop,(i*crop.width,35));draw.text((i*crop.width+8,10),'CURRENT SCAN' if i==0 else 'MATCHED SCAN',fill='black')
        for x,y in cloud:
            px=((x-ox)/resolution-x0)*scale+i*crop.width;py=(original.height-1-(y-oy)/resolution-y0)*scale+35
            draw.ellipse((px-1,py-1,px+1,py+1),fill=(230,30,30) if i==0 else (0,160,40))
    canvas.save(folder/'comparison.png')
    if args.apply:
        until=time.monotonic()+.7
        while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.025)
        assert report['confident'],'Ambiguous or insufficient improvement: no pose change applied'
        assert 'status' in state,'Cannot verify navigation action state'
        assert not any(s.status in (1,2,3) for s in state['status'].status_list),'Navigation is active; no pose reset applied'
        assert time.monotonic()-state.get('odom_at',-math.inf)<1,'Odometry stale'
        assert time.monotonic()-state.get('command_at',-math.inf)<1,'Command state stale'
        odom=state['odom'].twist.twist;command=state['command']
        assert abs(odom.linear.x)<.01 and abs(odom.angular.z)<.03 and abs(command.linear.x)+abs(command.angular.z)<.001,'Robot must be stationary'
        ex=extrinsic.transform.translation;eyaw=yaw(extrinsic.transform.rotation)
        byaw=best[2]-eyaw;c,s=math.cos(byaw),math.sin(byaw)
        message=PoseWithCovarianceStamped();message.header.frame_id='map';message.header.stamp=node.get_clock().now().to_msg()
        message.pose.pose.position.x=best[0]-c*ex.x+s*ex.y
        message.pose.pose.position.y=best[1]-s*ex.x-c*ex.y
        message.pose.pose.orientation.z=math.sin(byaw/2);message.pose.pose.orientation.w=math.cos(byaw/2)
        message.pose.covariance[0]=message.pose.covariance[7]=.05**2
        message.pose.covariance[35]=math.radians(3)**2
        publisher.publish(message)
        until=time.monotonic()+1.
        while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.05)
        report['applied']=True;report['base_pose']=[message.pose.pose.position.x,message.pose.pose.position.y,byaw]
    (folder/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True);print('Artifacts:',folder,flush=True)
    node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
