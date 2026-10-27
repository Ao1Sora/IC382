# Single-desk navigation module

The main program chooses a desk and owns the outer patrol loop and all inspection
operations. This module only plans and drives one desk's three inspection poses.
There is no autonomous desk loop, recognition stub, tagging stub, or timed work
completion inside the navigation server.

## Localization and map

The default entry now launches `desk_navigation.launch.py`, using the reviewed
map in `maps/inspection/`. It includes conservative table/chair bounds from the
annotated map. T01–T04 each have three poses in `config/desk_inspection_points.yaml`.
These were statically screened; camera visibility and all twelve poses have not
been independently certified. The controller still checks the full robot footprint.

Known start pose is configured explicitly, not read from Isaac ground truth:

```bash
./robot-ros2/scripts/hpc-patrol.sh start \
  initial_x:=-278.8637905602745 initial_y:=32.96996906027461 initial_yaw:=0.0
```

These are the original simulation spawn XY and heading, in the existing ten-times
map. They must match the actual starting pose. Start localization once at that
pose; do not restart it halfway through a run without supplying the current known
pose. A simulation reset or backwards clock requires reinitialization.

`map -> odom` is fixed at the configured start. `wheel_odometry` integrates the
measured left/right wheel velocities from `/joint_states` into `/odom` and publishes
`odom -> base_link`. There is no IMU and no AMCL/SLAM. Laser `/scan_nav` is used for
obstacle avoidance only. No command-velocity integration or simulator absolute pose
is used for localization. Encoder-only odometry accumulates slip and calibration
error; the known starting position does not eliminate that drift.

The default is standard differential-drive odometry: wheel radius `0.63` and both
track parameters `3.49`. An experimental **effective stationary-turn** track of
`4.316` scene units was measured offline on 2026-10-27:
integrated differential wheel travel / independently measured body turn =
8.83187 / 2.04672 = 4.31594. The geometric drive track remains `3.49`; it is not
the same parameter as the empirical stationary-turn track. With constant `3.49`, the first trial
completed T04-A but accumulated turn error and contacted a desk en route to T04-C;
the task was canceled. The calibration uses simulator truth only offline, never
as a live navigation input. This calibration is specific to this simulation model
and floor/contact settings, and does not compensate wheel spin against an obstacle.
Applying `4.316` to every rolling curve also produced substantial drift in a second
trial. A third trial blended from `turn_track=4.316` at zero linear speed to
`wheel_track=3.49` at `turn_blend_speed=0.5` scene units/second. It completed T04-A
but also drifted and contacted a desk en route to T04-C. This empirical blend is
available as an option but **disabled by default** by setting both tracks equal.
It is not a validated slip estimator. Override `wheel_radius:=... wheel_track:=...
turn_track:=... turn_blend_speed:=...` for a different model or physical robot.

The matching Isaac environment publishes measured wheel velocities and moves its
truth output to `/sim/ground_truth_odom` / `sim_ground_truth -> sim_base_link` for
diagnostics. It must not publish navigation's `/odom` or `odom -> base_link`.
Keep the environment and robot branch versions matched.

## Main-program interface

Action: `/ic382/inspect_desk`, type `ic382_interfaces/action/InspectDesk`.

```bash
ros2 action send_goal /ic382/inspect_desk ic382_interfaces/action/InspectDesk \
  "{desk_id: T04}" --feedback
```

Desk aliases `T04`, `T4`, `4`, and `TABLE_04` select the same desk. Invalid desks and
concurrent requests are rejected. A request waits for navigation readiness for up
to 90 wall-clock seconds, then fails with a reason rather than moving blindly.

1. Read the current estimated map pose. Ask Nav2 `ComputePathToPose` for the directed
   obstacle-aware path lengths from the current pose and between the remaining
   inspection poses.
2. Enumerate all six orders for three poses and choose the least total path length
   among feasible orders. This is an open route: no return to start is included.
   It is shortest among the returned Nav2 path combinations on the current costmap,
   not a claim of globally optimal continuous, nonholonomic or minimum-time motion.
3. Send the first pose, including its desk-facing heading, to `NavigateToPose`.
   Nav2 handles obstacle avoidance and route replanning during that movement.
4. Close the velocity gate after arrival. Wait for encoder speed and the final
   command to be near zero for at least 0.3 wall-clock seconds.
5. Publish `WAITING_FOR_WORK` with the task and point IDs. The main program performs
   recognition/tagging/other work and explicitly acknowledges completion.
6. After the acknowledgement and minimum dwell (default 1 second), re-plan the
   remaining poses from the new estimated position. After all three acknowledgements,
   return success once the terminal event is durably logged.

The module may change the order of unvisited poses as the obstacle map changes.
No point is revisited automatically. A completely unreachable three-pose route
fails before movement; dynamic failures return a reason with any completed points.

Service: `/ic382/complete_inspection`, type
`ic382_interfaces/srv/CompleteInspection`:

```bash
ros2 service call /ic382/complete_inspection ic382_interfaces/srv/CompleteInspection \
  "{task_id: '<task_id from feedback>', point_id: 'T04-C', success: true}"
```

Wrong task/point IDs, acknowledgements before the stopped-work state, and duplicates
are rejected. `success: false` ends the task as failed. No acknowledgement means
the robot stays stopped; default work timeout is 120 wall-clock seconds. Action
cancellation stops motion and returns the points already completed. The main program
must not send the next desk until the current action returns.

Feedback includes `task_id`, `state`, `point_id`, `visit_order`, and `completed_points`.
Result includes `success`, `message`, `visited_points`, and the initial planned route
length in scene units. Divide map distances/speeds by 10 for physical metres here.
`/ic382/mission_status` also exposes the current state, health, and log acknowledgement.

## Example caller and validation

```bash
source /workspace/robot-ros2/ros2_ws/install/setup.bash
python3 /workspace/robot-ros2/scripts/demo-inspect-desk.py \
  --desk T04 --work-seconds 3 --output /workspace/robot-ros2/results/desk-api-demo.json
```

This example is a MAIN-PROGRAM stub: it waits three seconds per stopped checkpoint
and sends the work acknowledgement. Replace that code with your actual operation.
The navigation server itself does not pretend an operation has happened.

Build both `ic382_interfaces` and `ic382_navigation` after updating. Existing teacher
ROS originals and the old `patrol.launch.py` remain for reference, but the default
entry no longer launches the patrol engine or AMCL. The final velocity gate,
sensor freshness checks, cancellation handling, and durable journal are retained.

An isolated ROS interface regression is also available. It runs the actual desk
action server, velocity gate and journal with fake Nav2 servers. It verifies the
three work handshakes, invalid/concurrent goals, wrong/duplicate acknowledgements,
zero commands while waiting and cancellation. It does not validate physical paths:

```bash
ROS_DOMAIN_ID=84 python3 scripts/check-desk-api.py --ros-args \
  -p points:=$(pwd)/ros2_ws/src/ic382_navigation/config/desk_inspection_points.yaml \
  -p log_directory:=/tmp/ic382-api-test-journal
```
