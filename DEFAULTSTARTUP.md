# Default startup verification — 2026-10-22

`start-course.sh` → `course601-desktop.sh` → `start-robot-navigation.sh` →
`robot-ros2/scripts/run-course-navigation.sh` → `ic382_navigation/patrol.launch.py`.

The runtime checks the local checkout branch is robot-ros2 and prints its commit. It does not
pull, rebuild, or send a navigation goal automatically. Course navigation and its old scan
adapter/initial-pose helpers are removed from the environment branch.

Verified on the existing HPC Isaac session:

- Robot checkout branch: robot-ros2; commit: d74f672.
- Loaded package prefix: /workspace/robot-ros2/ros2_ws/install/ic382_navigation.
- Mission state: IDLE; health: empty; motion_allowed: false.
- Sole /cmd_vel publisher: velocity_gate.
- 56 sampled output commands were all zero.
- Navigation and bringup: 18 tests, 0 errors/failures/skips.
- Nav2 managed nodes reached ACTIVE.

The velocity path retains Nav2's cmd_vel_nav input to the smoother. Smoothed output and
behavior-server recovery commands are routed through nav2_cmd_vel to the final gate.
A previous course component container that survived its launch parent's exit was explicitly
identified and stopped during migration. The manager now finishes stopping the verified
navigation process group even if a component hangs on shutdown.

This verifies the startup source and stationary readiness; it does not establish complete
multi-goal patrol or physical-robot acceptance.

After starting the simulation desktop, call from the HPC terminal:

```bash
cd ~/Desktop/IC382
./robot-ros2/scripts/hpc-ros.sh ros2 service call /ic382/start_mission std_srvs/srv/Trigger '{}'
```
