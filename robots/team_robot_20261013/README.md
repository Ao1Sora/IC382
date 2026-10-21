# Team robot CAD, 2026-10-13

Source: `建模第二版10.13(1).zip`, native SolidWorks assembly `建模/整体装配1.SLDASM`.
All 66 assembly component instances resolved in SolidWorks 2024. Its STL exporter produced 64 leaf-component files; the USD has 66 visual meshes after separating the two drive wheels.

- Original full CAD extent: approximately 0.390 m wide × 0.543 m long × 1.001 m tall in the supplied assembly pose.
- USD authored in meters, Z up; X forward corresponds to CAD +Y and Y left to CAD -X.
- Drive wheel radius: 0.063 m. Wheel track: 0.349 m. Both are inferred from supplied geometry.
- The loader inherits the old robot's wheel-axle spawn position. The legacy course scene uses a factor of 10; team_robot_scene.usdc bakes that factor into geometry, joint positions and inertia so rigid body transforms retain scale 1. The source team_robot.usdc remains authored at true CAD meter scale. The course building is unchanged.
- Course RTX lidar and ROS2 cmd_vel/odom/scan/clock interfaces are retained. Lidar mount is provisional; camera anchor does not implement a ROS camera publisher.
- Lift/tagging mechanisms retain the supplied assembly pose as chassis visuals and collision shapes; they have no actuator control yet.
- Chassis mass 12 kg plus 0.5 kg per drive wheel and inertia tensors are provisional simulation estimates, not measured values.
- Compound chassis/mechanism boxes, wheel cylinders and a low-friction spherical caster approximate collision geometry.

The server's existing desktop icon now launches `scripts/team-robot-simulation.py` through `scripts/course601-desktop.sh`.
The obsolete original-robot launcher and its backup are excluded from this branch snapshot.
Native CAD and intermediate STL files stay local; only the compact USD and integration scripts were uploaded to the server.

Live acceptance passed on 2026-10-21: ROS2 commanded forward displacement 0.394 scene units, yaw change 0.129 radians, stable height, growing clock/odom/scan counts. Articulation has left_wheel_joint and right_wheel_joint. A single-goal Nav2 smoke test also passed on 2026-10-21; the complete multi-goal patrol remains under validation. Navigation footprint, map scale and clearances must be retuned for this geometry and the legacy scene scale.
