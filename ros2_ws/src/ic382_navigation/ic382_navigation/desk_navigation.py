"""One-desk navigation action. The caller owns work and the outer patrol loop."""
import json
import math
from pathlib import Path
import threading
import time
import uuid
import yaml
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.task import Future
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import Odometry
from nav2_msgs.action import ComputePathToPose
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String
from tf2_ros import Buffer, TransformException, TransformListener
from ic382_interfaces.action import InspectDesk
from ic382_interfaces.srv import CompleteInspection
from .events import Events
from .inspection import canonical_desk, load_desks, shortest_visit_order
from .navigation import Navigator


class TaskFailure(RuntimeError):
    pass


class DeskNavigation(Node):
    def __init__(self):
        super().__init__('desk_navigation')
        self.group = ReentrantCallbackGroup()
        self.steady = Clock(clock_type=ClockType.STEADY_TIME)
        self.desks = load_desks(yaml.safe_load(Path(self.declare_parameter('points', '').value).read_text()))
        self.sensor_timeout = float(self.declare_parameter('sensor_timeout', 5.).value)
        self.minimum_dwell = float(self.declare_parameter('minimum_dwell_seconds', 1.).value)
        self.work_timeout = float(self.declare_parameter('work_timeout_seconds', 120.).value)
        self.nav_timeout = float(self.declare_parameter('navigation_timeout', 600.).value)
        if self.sensor_timeout <= 0 or self.work_timeout <= 0 or self.minimum_dwell < 0 or self.minimum_dwell >= self.work_timeout:
            raise ValueError('Invalid timing parameters')
        self.tf = Buffer(); self.listener = TransformListener(self.tf, self)
        self.scan_at = self.odom_at = self.logger_at = -math.inf
        self.logger_ok = False; self.nav2_active = False
        self.lifecycle_at = -math.inf; self.lifecycle_pending = False
        self.log_ack = 0; self.last_ack_at = time.monotonic()
        self.state = 'IDLE'; self.task_id = ''; self.desk_id = ''; self.point_id = ''
        self.order = []; self.visited = []; self.work_result = None
        self.planned_length = 0.; self.odom_speed = (math.inf, math.inf)
        self.final_command = (math.inf, math.inf)
        self.reserved = False; self.lock = threading.Lock(); self.task_handle = None
        self.events = Events(self, uuid.uuid4().hex)
        self.nav = Navigator(self, self.health, self.events.emit, self.nav_timeout)
        self.allow = self.create_publisher(Bool, '/ic382/allow_motion', 10)
        self.status = self.create_publisher(String, '/ic382/mission_status', 10)
        self.create_subscription(LaserScan, 'scan_nav', self.scan, qos_profile_sensor_data, callback_group=self.group)
        self.create_subscription(Odometry, 'odom', self.odom, qos_profile_sensor_data, callback_group=self.group)
        self.create_subscription(Twist, 'cmd_vel', self.command, 10, callback_group=self.group)
        self.create_subscription(Bool, '/ic382/logger_ready', self.logger, 10, callback_group=self.group)
        self.create_subscription(String, '/ic382/log_ack', self.ack, 100, callback_group=self.group)
        self.lifecycle = self.create_client(GetState, '/bt_navigator/get_state', callback_group=self.group)
        self.planner = ActionClient(self, ComputePathToPose, 'compute_path_to_pose', callback_group=self.group)
        self.create_service(CompleteInspection, '/ic382/complete_inspection', self.complete_work, callback_group=self.group)
        self.server = ActionServer(self, InspectDesk, '/ic382/inspect_desk', self.execute,
                                  goal_callback=self.accept, cancel_callback=self.cancel, callback_group=self.group)
        self.create_timer(.1, self.tick, clock=self.steady, callback_group=self.group)

    def scan(self, msg):
        if msg.ranges:self.scan_at = time.monotonic()

    def odom(self, msg):
        self.odom_at = time.monotonic()
        self.odom_speed = (msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def command(self, msg):
        self.final_command = (msg.linear.x, msg.angular.z)

    def logger(self, msg):
        self.logger_ok, self.logger_at = msg.data, time.monotonic()

    def ack(self, msg):
        try:
            d = json.loads(msg.data)
            if d.get('run_id') == self.events.run_id and d.get('source') == self.get_name() and isinstance(d.get('seq'), int):
                self.log_ack = max(self.log_ack, d['seq']); self.last_ack_at = time.monotonic()
        except (ValueError, TypeError):pass

    def health(self):
        now = time.monotonic()
        for name, stamp in [('scan', self.scan_at), ('odometry', self.odom_at)]:
            if now-stamp > self.sensor_timeout:return name+'_stale'
        if not self.logger_ok or now-self.logger_at > self.sensor_timeout:return 'logger_unavailable'
        if self.events.seq > self.log_ack and now-self.last_ack_at > 5:return 'journal_ack_timeout'
        if not self.nav2_active or now-self.lifecycle_at > 10:return 'nav2_inactive'
        if not self.tf.can_transform('map', 'base_footprint', rclpy.time.Time()):return 'map_pose_unavailable'
        try:transform = self.tf.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        except TransformException:return 'map_pose_unavailable'
        stamp = transform.header.stamp.sec+transform.header.stamp.nanosec/1e9
        if self.get_clock().now().nanoseconds/1e9-stamp > 2:return 'odometry_transform_stale'
        return ''

    def tick(self):
        now = time.monotonic()
        if not self.lifecycle_pending and now-self.lifecycle_at > 2 and self.lifecycle.service_is_ready():
            self.lifecycle_pending = True
            self.lifecycle.call_async(GetState.Request()).add_done_callback(self.lifecycle_result)
        moving = self.state == 'NAVIGATING' and self.nav.motion_allowed
        self.allow.publish(Bool(data=moving))
        status = {'run_id': self.task_id, 'task_id': self.task_id, 'state': self.state,
                  'desk_id': self.desk_id, 'point_id': self.point_id, 'visit_order': self.order,
                  'visited_points': self.visited, 'health': self.health(), 'motion_allowed': moving,
                  'journal_confirmed': self.state in ('COMPLETED','FAILED','CANCELED') and self.log_ack >= self.events.seq}
        self.status.publish(String(data=json.dumps(status)))
        handle = self.task_handle
        if handle is not None and handle.is_active:
            feedback = InspectDesk.Feedback()
            feedback.task_id = self.task_id; feedback.state = self.state; feedback.point_id = self.point_id
            feedback.visit_order = self.order; feedback.completed_points = len(self.visited)
            handle.publish_feedback(feedback)

    def lifecycle_result(self, future):
        self.lifecycle_pending = False; self.lifecycle_at = time.monotonic()
        try:self.nav2_active = future.result().current_state.id == 3
        except Exception:self.nav2_active = False

    def accept(self, request):
        with self.lock:
            if canonical_desk(request.desk_id) not in self.desks or self.reserved or self.nav.pending:
                return GoalResponse.REJECT
            self.reserved = True
        return GoalResponse.ACCEPT

    def cancel(self, handle):
        self.allow.publish(Bool(data=False))
        if self.nav.pending:self.nav.cancel('operator_cancelled')
        return CancelResponse.ACCEPT

    def check(self, healthy=True):
        if self.task_handle is not None and self.task_handle.is_cancel_requested:raise TaskFailure('operator_cancelled')
        if healthy and self.health():raise TaskFailure(self.health())

    async def wait(self, predicate, timeout, healthy=True, label='wait'):
        future = Future(); deadline = time.monotonic()+timeout
        def poll():
            if future.done():return
            try:
                self.check(healthy)
                if predicate():future.set_result(True)
                elif time.monotonic()>deadline:raise TaskFailure(label+'_timeout')
            except Exception as exc:future.set_exception(exc)
        timer = self.create_timer(.05, poll, clock=self.steady, callback_group=self.group)
        try:return await future
        finally:self.destroy_timer(timer)

    def pose(self):
        tf = self.tf.lookup_transform('map','base_footprint',rclpy.time.Time()).transform
        q=tf.rotation
        return {'x':tf.translation.x,'y':tf.translation.y,
                'yaw':math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))}

    def stamped(self, p):
        msg=PoseStamped();msg.header.frame_id='map';msg.header.stamp=self.get_clock().now().to_msg()
        msg.pose.position.x=float(p['x']);msg.pose.position.y=float(p['y'])
        msg.pose.orientation.z=math.sin(p['yaw']/2);msg.pose.orientation.w=math.cos(p['yaw']/2)
        return msg

    async def path_length(self, start, goal):
        request=ComputePathToPose.Goal();request.start=self.stamped(start);request.goal=self.stamped(goal)
        request.use_start=True;request.planner_id='GridBased'
        future=self.planner.send_goal_async(request)
        await self.wait(future.done,20,label='planner_acceptance')
        handle=future.result()
        if not handle.accepted:return math.inf
        result=handle.get_result_async()
        try:await self.wait(result.done,20,label='planner_result')
        except Exception:
            handle.cancel_goal_async();raise
        response=result.result()
        if response.status!=GoalStatus.STATUS_SUCCEEDED:return math.inf
        poses=response.result.path.poses
        if not poses:return math.inf
        return sum(math.hypot(b.pose.position.x-a.pose.position.x,b.pose.position.y-a.pose.position.y)
                   for a,b in zip(poses,poses[1:]))

    async def plan(self, points):
        self.state='PLANNING';self.allow.publish(Bool(data=False))
        await self.wait(self.planner.server_is_ready,15,label='planner_ready')
        current=self.pose();costs={}
        for goal in points:
            costs[(None,goal['id'])]=await self.path_length(current,goal)
        for start in points:
            for goal in points:
                if start['id']!=goal['id']:costs[(start['id'],goal['id'])]=await self.path_length(start,goal)
        order,length=shortest_visit_order(points,costs)
        self.order=list(self.visited)+[p['id'] for p in order]
        self.events.emit('inspection_route_planned',{'desk_id':self.desk_id,'visit_order':self.order,
            'remaining_path_length':length,'costs':[{'from':a or 'CURRENT','to':b,'length':v if math.isfinite(v) else None} for (a,b),v in costs.items()]})
        return order,length

    def complete_work(self, request, response):
        with self.lock:
            if self.state!='WAITING_FOR_WORK' or request.task_id!=self.task_id or request.point_id!=self.point_id:
                response.accepted=False;response.message='No matching stopped checkpoint';return response
            if self.work_result is not None:
                response.accepted=False;response.message='Checkpoint already acknowledged';return response
            self.work_result=bool(request.success)
            response.accepted=True;response.message='Work result accepted; minimum dwell still enforced'
        return response

    async def execute(self, handle):
        self.task_handle=handle;self.task_id=uuid.uuid4().hex;self.desk_id=canonical_desk(handle.request.desk_id)
        self.point_id='';self.visited=[];self.order=[];self.planned_length=0.
        self.events.run_id=self.task_id;self.events.seq=0;self.log_ack=0;self.last_ack_at=time.monotonic()
        result=InspectDesk.Result();result.task_id=self.task_id
        try:
            self.state='PREPARING'
            await self.wait(lambda:not self.health() and self.nav.client.server_is_ready(),90,healthy=False,label='navigation_ready')
            self.events.emit('desk_inspection_started',{'desk_id':self.desk_id,'localization':'wheel_dead_reckoning'})
            remaining=list(self.desks[self.desk_id])
            while remaining:
                order,length=await self.plan(remaining)
                if not self.visited:self.planned_length=length
                point=order[0];self.point_id=point['id'];self.state='NAVIGATING'
                self.events.emit('inspection_navigation_requested',point)
                self.nav.start(point,time.monotonic())
                await self.wait(lambda:self.nav.poll(time.monotonic()) is not None,self.nav_timeout+1,label='navigation')
                outcome=self.nav.poll(time.monotonic())
                if outcome!='SUCCEEDED':raise TaskFailure(str(outcome))
                self.state='STOPPING';self.allow.publish(Bool(data=False))
                stopped_since=[None]
                def stopped():
                    ok=abs(self.odom_speed[0])<.05 and abs(self.odom_speed[1])<.03 and max(map(abs,self.final_command))<.001
                    if not ok:stopped_since[0]=None
                    elif stopped_since[0] is None:stopped_since[0]=time.monotonic()
                    return stopped_since[0] is not None and time.monotonic()-stopped_since[0]>=.3
                await self.wait(stopped,15,label='settle')
                self.work_result=None;self.state='WAITING_FOR_WORK';arrived=time.monotonic()
                self.events.emit('inspection_point_ready',{'point_id':self.point_id,'desk_id':self.desk_id})
                await self.wait(lambda:self.work_result is not None,self.work_timeout,label='work')
                if not self.work_result:raise TaskFailure('inspection_operation_failed')
                await self.wait(lambda:time.monotonic()-arrived>=self.minimum_dwell,self.minimum_dwell+1,label='dwell')
                self.visited.append(self.point_id)
                self.events.emit('inspection_point_completed',{'point_id':self.point_id})
                remaining=[p for p in remaining if p['id']!=self.point_id]
            self.state='COMPLETED';self.events.emit('desk_inspection_completed',{'desk_id':self.desk_id,'visited_points':self.visited})
            await self.wait(lambda:self.log_ack>=self.events.seq,5,healthy=False,label='journal')
            result.success=True;result.message='Three inspection points completed and logged';handle.succeed()
        except Exception as exc:
            self.nav.cancel(str(exc));self.allow.publish(Bool(data=False))
            canceled=handle.is_cancel_requested
            self.state='CANCELED' if canceled else 'FAILED'
            self.events.emit('desk_inspection_'+self.state.lower(),{'reason':str(exc),'visited_points':self.visited})
            result.success=False;result.message=str(exc)
            if canceled:handle.canceled()
            else:handle.abort()
        finally:
            self.allow.publish(Bool(data=False));result.visited_points=list(self.visited)
            result.planned_path_length=self.planned_length
            self.task_handle=None
            with self.lock:self.reserved=False
        return result


def main(args=None):
    rclpy.init(args=args);node=DeskNavigation();executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    try:executor.spin()
    except KeyboardInterrupt:pass
    finally:
        node.allow.publish(Bool(data=False));executor.shutdown();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
