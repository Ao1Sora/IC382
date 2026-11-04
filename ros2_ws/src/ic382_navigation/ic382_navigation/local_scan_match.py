"""Bounded scan/map refinement around a manually established pose."""
import math
import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates


def alignment_supports_navigation(result):
    """A rejected correction at the boundary is not itself loss of localization."""
    return bool(result['healthy'] and (not result['boundary'] or result['before_score']>=.70))


class LocalScanMatcher:
    def __init__(self, grid, resolution, origin=(0.,0.,0.), translation=.12,
                 rotation=math.radians(6)):
        self.grid=np.asarray(grid)
        self.resolution=float(resolution)
        self.origin=np.asarray(origin)
        self.translation=translation;self.rotation=rotation
        self.known=(self.grid>=0).astype(float)
        self.distance=distance_transform_edt(~(self.grid>=65))*resolution
        # Coarse search followed by a fine neighbourhood keeps the enlarged
        # local window affordable at 1 Hz on the Jetson.
        values=np.arange(-translation,translation+.005,.02)
        dx,dy=np.meshgrid(values,values)
        offsets=np.column_stack((dx.ravel(),dy.ravel()))
        offsets=offsets[np.linalg.norm(offsets,axis=1)<=translation+1e-6]
        self.offsets=np.vstack([np.column_stack((offsets,np.full(len(offsets),a)))
            for a in np.arange(-rotation,rotation+math.radians(.125),math.radians(.5))])
        self.prior=.015*np.sum((self.offsets[:,:2]/translation)**2,axis=1)+.015*(self.offsets[:,2]/rotation)**2

    def residuals(self, points, poses):
        poses=np.asarray(poses).reshape(-1,3)
        c=np.cos(poses[:,2,None]);s=np.sin(poses[:,2,None])
        x=poses[:,0,None]+c*points[None,:,0]-s*points[None,:,1]-self.origin[0]
        y=poses[:,1,None]+s*points[None,:,0]+c*points[None,:,1]-self.origin[1]
        oc,os=math.cos(self.origin[2]),math.sin(self.origin[2])
        col=(oc*x+os*y)/self.resolution-.5
        row=(-os*x+oc*y)/self.resolution-.5
        coordinates=[row.ravel(),col.ravel()]
        result=map_coordinates(self.distance,coordinates,order=1,mode='constant',cval=2.).reshape(x.shape)
        known=map_coordinates(self.known,coordinates,order=0,mode='constant',cval=0.).reshape(x.shape)
        result[known<.5]=2.
        return result

    def match(self, points, pose):
        points=np.asarray(points)
        candidates=np.asarray(pose)+self.offsets
        residuals=self.residuals(points,candidates)
        scores=np.mean(np.exp(-.5*(residuals/.08)**2),axis=1)
        index=int(np.argmax(scores-self.prior))
        coarse=self.offsets[index]
        fine=np.array([coarse+[x,y,a] for x in (-.01,0.,.01)
            for y in (-.01,0.,.01) for a in (-math.radians(.25),0.,math.radians(.25))])
        fine=fine[(np.linalg.norm(fine[:,:2],axis=1)<=self.translation+1e-9)&
                  (np.abs(fine[:,2])<=self.rotation+1e-9)]
        residuals=self.residuals(points,np.asarray(pose)+fine)
        scores=np.mean(np.exp(-.5*(residuals/.08)**2),axis=1)
        prior=.015*np.sum((fine[:,:2]/self.translation)**2,axis=1)+.015*(fine[:,2]/self.rotation)**2
        index=int(np.argmax(scores-prior))
        offset=fine[index].copy()
        before=self.residuals(points,[pose])[0]
        baseline=float(np.mean(np.exp(-.5*(before/.08)**2)))
        quality=float(scores[index]);inliers=float(np.mean(residuals[index]<.10))
        boundary=bool(np.linalg.norm(offset[:2])>=self.translation-.005 or
            abs(offset[2])>=self.rotation-math.radians(.125))
        healthy=bool(baseline>=.50 and np.mean(before<.10)>=.50)
        # Only apply a small, clearly improving correction inside the search box.
        apply=bool(not boundary and quality>=.55 and inliers>=.55 and quality-baseline>=.005)
        correction=offset*.75
        length=np.linalg.norm(correction[:2])
        if length>.06:correction[:2]*=.06/length
        correction[2]=np.clip(correction[2],-math.radians(4),math.radians(4))
        if np.linalg.norm(correction[:2])<.004 and abs(correction[2])<math.radians(.1):apply=False
        return dict(offset=offset,correction=correction,before_score=baseline,
            after_score=quality,inliers=inliers,boundary=boundary,healthy=healthy,apply=apply)


def propagate_pose(corrected, odom_at_scan, odom_latest, velocity, delay):
    """Carry a scan-time correction to publication time in SE(2).

    Humble AMCL can fail its lookup at now and use an identity delta. Never
    send a moving robot's past pose and rely on that lookup succeeding.
    """
    corrected=np.asarray(corrected,dtype=float)
    old=np.asarray(odom_at_scan);new=np.asarray(odom_latest)
    angle=corrected[2]-old[2]
    c,s=math.cos(angle),math.sin(angle)
    delta=new[:2]-old[:2]
    result=corrected+np.array([c*delta[0]-s*delta[1],s*delta[0]+c*delta[1],new[2]-old[2]])
    result[2]=math.atan2(math.sin(result[2]),math.cos(result[2]))
    vx,vy,w=velocity
    a=w*delay
    if abs(w)>1e-7:
        dx=(vx*math.sin(a)+vy*(math.cos(a)-1))/w
        dy=(vx*(1-math.cos(a))+vy*math.sin(a))/w
    else:dx,dy=vx*delay,vy*delay
    c,s=math.cos(result[2]),math.sin(result[2])
    result[:2]+=[c*dx-s*dy,s*dx+c*dy]
    result[2]=math.atan2(math.sin(result[2]+a),math.cos(result[2]+a))
    return result
