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

Both global and local costmaps load this static map. The local static layer is
essential: the low lidar can see table legs while missing the overhanging top.
Without it, DWB can cut through the tabletop projection even when the global
planner avoids it. Footprint padding is 0.75 scene units (7.5 cm physical);
inflation radius is 8.0 with cost scaling 0.3 for the ten-times scene.

The teacher-derived DWB tracker is wrapped by the upstream Humble
`nav2_rotation_shim_controller::RotationShimController`. It first rotates into the
new path's heading, avoiding the alternating turn commands observed when departing
a desk facing away from the route. It also handles final desk-facing rotation.
Rotations still use full-footprint collision checking; they never bypass the map.
Slow reverse motion is allowed down to -0.5 scene units/s for clearance maneuvers.

The old candidate T04-C was clear only at its final heading, but did not have
enough room to rotate the padded robot. T04's three points now retain their east,
west and south viewing directions and are shifted outward by 4.0, 3.25 and 4.5
scene units respectively (40, 32.5 and 45 cm physical). Each has a statically free
10.5-scene-unit turning circle, versus the padded footprint's roughly 6.7-unit
maximum radius. Current coordinates are authoritative in the YAML; older annotated
map images show the original candidates. Camera coverage remains unverified.
Other desks remain candidates and have not received this same turning-circle
certification. Screen them separately rather than assuming all twelve were tested.

The reproducible geometry-screening command is:

```bash
python3 scripts/prepare-inspection-points.py \
  --map ros2_ws/src/ic382_navigation/maps/inspection/scene_map.yaml \
  --points ros2_ws/src/ic382_navigation/config/desk_inspection_points.yaml \
  --output /tmp/screened-inspection-points.yaml --desk T04 --clearance 10.5
```

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
measured left/right wheel angles from `/joint_states` into `/odom` and publishes
`odom -> base_link`. There is no IMU and no AMCL/SLAM. Laser `/scan_nav` is used for
obstacle avoidance only. No command-velocity integration or simulator absolute pose
is used for localization. Encoder-only odometry accumulates slip and calibration
error; the known starting position does not eliminate that drift.

Angle increments are preferred over sampled velocity integration: they preserve
the distance traveled between messages, including acceleration and periodic joint
coordinate wrapping. Publishers must supply sufficiently frequent samples that
each wheel moves less than pi radians between messages. If a publisher supplies
only velocities, the older trapezoidal velocity integrator is used. Changing modes
mid-run is rejected and requires localization reinitialization.

These wheel samples are available in **Isaac**, not yet verified on the physical
course chassis. Course materials reference `turn_on_wheeltec_robot` but do not
include that driver's source. Before physical integration, inspect the actual
Jetson driver and its `/odom`, wheel feedback and serial protocol; do not assume
that independent wheel velocities or `/joint_states` are exposed. If the chassis
already provides suitable odometry, select `odometry_source:=external`: this omits
the simulator wheel-odometry node and consumes the external `/odom` and TF.
There must be a single odometry/TF publisher and a continuous odom frame whose
origin matches the configured known-start map anchor. This mode has not been
verified on the physical chassis. Physical maps/points must use real metres;
the default ten-times simulation points intentionally block `use_sim_time:=false`.

The launch uses a constant differential-drive model with effective wheel radius
`0.630835` and effective track `3.611644` scene units. Both track parameters are
identical, so the optional scrub blend is disabled. Physical scene geometry remains
radius `0.63` / track `3.49`; `base_height=0.63` is kept separate from the calibrated
kinematic radius so the ground TF does not move when calibrating odometry.

These constants were fitted **offline** from stopped T04-A and T04-C observations
under the repaired contact profile. T04-B was held out: replay prediction reduced
its odometry-position discrepancy from about 42 cm to 5.7 cm. A fresh physical
simulation run then completed all three points: measured parking errors were
4.6 / 5.4 / 4.2 cm for A / C / B, while final odometry discrepancy was about 9.1 cm.
The physical C parking error is slightly above the configured 5 cm estimated-pose
tolerance; estimated-pose action success is not a guarantee of physical accuracy.
See [measured validation](validation/navigation-repair-20261027.json).
Truth is used by the offline calibration/validation tools only, never by the live
odometry node. Different contact settings or physical hardware need new calibration.
Old `4.316` stationary-turn estimates predate the contact repair and must not be reused.

`calibrate-wheel-odometry.py` requires the full estimated trajectory when the truth
audit starts late; treating missed initial motion as one arc gives an invalid fit.
It fits two checkpoints and reports a separately held-out checkpoint. A synthetic
known-bias regression verifies the recovered constants and holdout prediction.

The matching Isaac environment publishes measured wheel velocities and moves its
truth output to `/sim/ground_truth_odom` / `sim_ground_truth -> sim_base_link` for
diagnostics. It must not publish navigation's `/odom` or `odom -> base_link`.
Keep the environment and robot branch versions matched.

The matching contact profile explicitly binds the drive-wheel physics material
(static/dynamic friction 1.2/0.9, max combine), makes the fixed-sphere caster
approximation frictionless (min combine), and initializes articulation contact
solver iterations to 64/16. Teacher/CAD assets and streamed resolution are unchanged.
Earlier effective-track measurements predate this contact repair and must not be
reused as calibration for the updated physics without revalidation.

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
