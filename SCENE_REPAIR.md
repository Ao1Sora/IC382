# Course scene material and physics repair

The normal team-robot launcher now builds `cache/course-scene-repaired.usda`
before attaching the course scene. The teacher USD and the existing clean USD
are never overwritten. Regeneration is automatic on every launch.

The overlay masks the inherited `/World` grey material binding, restores
unambiguous asset references using the existing course assets, bundled MDL
library and (when available) the downloaded teacher archive, and retains original
material bindings. It prefers a complete copy of an MDL module when duplicate
copies exist. Materials whose files or internal texture dependencies are absent
receive a portable PreviewSurface using authored color/roughness/metallic/opacity
and available base-color textures. These substitutes cannot reproduce missing
original images. A per-asset and per-material manifest is written beside the
generated overlay as `cache/course-scene-repaired.json`.

`/World/IC_building_scene/Cube_02` is now fixed scenery with static triangle-mesh
collision. This removes PhysX's dynamic-triangle-mesh convex-hull fallback.
The team's geometry and inertias are already baked at scene scale 10, so the
simulation gravity is now `9.81 * scene_scale` (98.1 scene units/s²). This keeps
the existing map and ROS coordinates while correcting free-fall time scaling.
It is not a full calibration of real robot drive gains or contact friction.
Robot spawn height and wheel geometry are unchanged.

Wheel velocity damping now scales as `100 * scene_scale` (1000 in this scene)
so low-speed wheel commands can track against the scaled gravity/contact loads.
This was tested with the robot-ros2 table-side profile: a TABLE_04 goal completed
and logged, with a sampled peak command of 0.3466 m/s and zero final command.

Validation on HPC job 139704, h07g02, 2026-10-27:

- Original floor material binding restored; global grey binding masked.
- Architectural Cube_02 has rigid-body simulation disabled, collision enabled.
- Runtime gravity verified as 98.0999985 scene units/s².
- Three-second low-speed drive probe moved about 1.95 scene units (19.5 cm).
  Robot stopped upright; settled Z variation after the probe was below 0.00018
  scene units (0.018 mm at physical scale).
- RTX lidar passed with 3600 finite returns; 198 scan messages in the drive run.
- Diagnostic copies run separately without navigation and exit automatically.
  This is not an end-to-end navigation route acceptance test.

The fixed 1920×1080 streaming settings and the desktop script's client-wait/EXIT
cleanup behavior are retained. Start the simulation through the existing desktop
entry. Close the client window to stop the simulation as before.

To revert, use the previous Git version of `scripts/team-robot-simulation.py`;
generated cache files are not loaded by that version. No teacher asset rollback
is needed.
