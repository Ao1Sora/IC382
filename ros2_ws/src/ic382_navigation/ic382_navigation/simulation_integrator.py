"""Isaac encoder integration retained from the tested HPC adapter."""
import math

class WheelIntegrator:
    def __init__(self, radius, track, maximum_dt=.5, turn_track=None, turn_blend_speed=.5):
        turn_track = track if turn_track is None else turn_track
        if not all(math.isfinite(v) and v > 0 for v in (radius, track, maximum_dt, turn_track, turn_blend_speed)):
            raise ValueError('Wheel dimensions and maximum_dt must be positive')
        self.radius, self.track, self.maximum_dt = radius, track, maximum_dt
        self.turn_track, self.turn_blend_speed = turn_track, turn_blend_speed
        self.x = self.y = self.yaw = 0.
        self.previous = None
        self.previous_positions = None

    def update_positions(self, stamp, left, right):
        """Integrate encoder angles, including periodic joint-angle wrapping."""
        if not all(math.isfinite(v) for v in (stamp, left, right)):
            raise ValueError('Non-finite encoder sample')
        if self.previous_positions is None:
            if self.previous is not None:
                raise ValueError('Encoder input mode changed; reinitialize localization')
            self.previous_positions = (stamp, left, right)
            self.previous = (stamp, 0., 0.)
            return self.x, self.y, self.yaw, 0., 0.
        old_stamp, old_left, old_right = self.previous_positions
        dt = stamp-old_stamp
        if dt <= 0 or dt > self.maximum_dt:
            raise ValueError('Encoder clock/gap invalid; reinitialize localization')
        # Supported rates keep actual increments below pi rad/sample. Wrapping
        # also handles Isaac's periodic joint coordinates without a false jump.
        dl = self.radius * math.atan2(math.sin(left-old_left), math.cos(left-old_left))
        dr = self.radius * math.atan2(math.sin(right-old_right), math.cos(right-old_right))
        distance = (dl+dr)/2
        v = distance/dt
        rolling = min(1., abs(v)/self.turn_blend_speed)
        track = self.turn_track+rolling*(self.track-self.turn_track)
        angle = (dr-dl)/track
        if abs(angle) < 1e-8:
            self.x += distance*math.cos(self.yaw)
            self.y += distance*math.sin(self.yaw)
        else:
            self.x += distance/angle*(math.sin(self.yaw+angle)-math.sin(self.yaw))
            self.y -= distance/angle*(math.cos(self.yaw+angle)-math.cos(self.yaw))
        self.yaw = math.atan2(math.sin(self.yaw+angle), math.cos(self.yaw+angle))
        self.previous_positions = (stamp,left,right)
        self.previous = (stamp,v,angle/dt)
        return self.x,self.y,self.yaw,v,angle/dt

    def update(self, stamp, left, right):
        if self.previous_positions is not None:
            raise ValueError('Encoder input mode changed; reinitialize localization')
        if not all(math.isfinite(v) for v in (stamp, left, right)):
            raise ValueError('Non-finite encoder sample')
        v = self.radius * (left + right) / 2
        # Static turns have different scrub from rolling curves in this scene.
        # Both tracks are offline calibration constants, not pose observations.
        rolling = min(1., abs(v) / self.turn_blend_speed)
        effective_track = self.turn_track + rolling * (self.track - self.turn_track)
        w = self.radius * (right - left) / effective_track
        if self.previous is not None:
            old_stamp, old_v, old_w = self.previous
            dt = stamp - old_stamp
            if dt <= 0:
                raise ValueError('Encoder clock must increase; restart localization after a simulation reset')
            if dt > self.maximum_dt:
                raise ValueError('Encoder gap exceeds integration limit; localization must be reinitialized')
            speed, omega = (v + old_v) / 2, (w + old_w) / 2
            end = self.yaw + omega * dt
            if abs(omega) < 1e-8:
                self.x += speed * dt * math.cos(self.yaw)
                self.y += speed * dt * math.sin(self.yaw)
            else:
                self.x += speed / omega * (math.sin(end) - math.sin(self.yaw))
                self.y -= speed / omega * (math.cos(end) - math.cos(self.yaw))
            self.yaw = math.atan2(math.sin(end), math.cos(end))
        self.previous = (stamp, v, w)
        return self.x, self.y, self.yaw, v, w
