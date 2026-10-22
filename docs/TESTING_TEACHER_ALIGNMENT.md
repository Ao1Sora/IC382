# Teacher-derived navigation validation — 2026-10-22

Code under test: `6bf90c3`, branch `robot-ros2`, deployed to the existing HPC
Isaac Sim 6.0.1 scene. No physical robot was tested.

## Automated checks

`colcon build` and `colcon test` for `ic382_navigation` and `ic382_bringup`:
24 tests passed, zero errors, failures or skips. Regenerating the static profile
from the unchanged teacher YAML and team overrides matched the committed
`nav2_course.yaml` byte for byte.

## Actual short navigation test

Run ID: `b50e803a3c82493585f8b165e4f873c1`.
One goal, `REF_SMOKE`, approximately 4 scene units forward (0.4 physical metres),
with a requested yaw change of 0.6 radians. Target map pose:
`[-277.01107756881754, 31.86842917529496, 0.6038862304552496]`.

- Mission reached `COMPLETED`, with `journal_confirmed=true`.
- Independent simulator position error: 0.42478048 scene units,
  approximately 4.25 cm at scene scale 10 (configured tolerance: 5 cm).
- Independent simulator yaw error: -0.19469505 rad, approximately -11.16 degrees
  (configured tolerance: 0.2 rad, approximately 11.46 degrees).
- Inspection and tagging placeholders each ran for 3 simulated seconds.
- Observed nonzero commands during placeholder dwell: 0.
- Final commanded linear and angular speeds: `[0.0, 0.0]`.
- Approximately 147 seconds wall time including ROS startup and readiness.

Independent pose samples are verification evidence only; they are not fed back
to the navigation controller. AMCL handles localization after one-time startup
initialization. Measurements use the latest simulator snapshot when the success
event is received and therefore include snapshot/event timing differences.
The heading result is close to the configured acceptance boundary; this short
test does not establish tighter heading precision.

Live ROS graph: `/cmd_vel` had exactly one publisher, `velocity_gate`.
Map server loaded the installed `ic382_navigation/maps/course/scene_map.yaml`.
Teacher original SHA-256 remained
`fd50817f337a30fac957b49d2fb29a8001496ed1962e2e0ee20a1a244b0a553f`;
team map PGM remained
`51c0383ed9356fc4ec5e2132ea86d79cb82164f1fa99e2dc24a9e87f147aa22b`.

Raw evidence remains at `results/teacher-reference-smoke.json` locally and in the
HPC checkout. Generated runtime results are ignored by Git. The default two-round
demonstration route is restored after testing, with motion awaiting an explicit
mission start.

## Scope

This verifies one translation plus terminal rotation and placeholder/logging
sequence. It does not verify the full multi-table route, dynamic-obstacle trials,
real recognition/tag placement, or hardware operation. Earlier full-route
`scan_stale` failures are not considered resolved by this short test.
