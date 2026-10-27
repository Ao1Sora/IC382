# Table-side simulation demonstration

Use the real teacher-scene object `/World/IC_building_scene/objects/table_04` as
the demonstration destination. Its XY bounds are approximately
[-293.1834, -275.2211] × [48.3994, 55.8642] in the existing ten-times scene.
`config/table_04_demo_route.yaml` requests the south-side stopping pose
(-284.2022, 40.5), facing north. This is a simulation object label, not a verified
assessment desk ID. Vision inspection and tagging remain timed three-second
placeholders.

The team profile permits 3.5 scene units/s (0.35 m/s) and 0.6 rad/s. The DWB,
velocity smoother, and final velocity gate use consistent limits. Localization
updates are requested after 0.05 scene units or 0.03 radians of movement.
Collision checking, the CAD footprint, sensor watchdogs, and final command gate
remain active.

DWB previously inherited a two-unit forward pruning distance. In this scene
that exposes only 20 cm of path and can favor roughly one scene unit/s with a
two-second rollout, even when the maximum velocity is increased. The explicit
forward/back pruning distances are now ten scene units; the forward path covers
a maximum-speed rollout. A regression test checks this relationship.

The simulation environment also needs the matching wheel-drive response:
`100 * scene_scale` angular velocity damping instead of a fixed 100. The ten-times
scene uses 1000, matching the increased gravity scale's contact loads. This is
an Isaac simulation setting; it is not a motor tuning recommendation for the
physical robot.

Run through the existing HPC simulation and robot-ros2 checkout. For this route,
pass `/workspace/robot-ros2/ros2_ws/src/ic382_navigation/config/table_04_demo_route.yaml`
to `scripts/hpc-patrol.sh start`, then invoke `/ic382/start_mission` after the
mission reports healthy IDLE. Do not run another Nav2 instance alongside it.

HPC validation on 2026-10-27: 21 tests passed. Run
`8437acab47624bbd92dca5f1e07f0b26` reached TABLE_04 and finished the timed inspection
and tagging placeholders with journal-confirmed COMPLETED. Peak sampled velocity
command was 0.3466 m/s; the final command was zero and no nonzero commands were
observed during the dwell stages. Independent simulator position error at arrival
was 0.0189 m. Observed heading error was 0.212 radians, close to but slightly above
the 0.2-radian configured tolerance; this is not independent precision acceptance.

The 30.8-second video includes the actual Nav2 plan, simulator trajectory and a
5.9-times wall-clock playback label. The simulator was reset to its starting pose
before the recorded mission; no pose resets or ground-truth localization updates
were used during navigation. A single destination demonstration is not a complete
patrol-route acceptance.
