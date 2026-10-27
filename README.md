# IC382 Robot ROS2 Workspace

The **robot-ros2** branch is the team's workspace for perception, navigation, mission logic, and interface packages.
The simulation environment is maintained separately on [hpc-isaac-sim-env](https://github.com/Ao1Sora/IC382/tree/hpc-isaac-sim-env).
Keep Isaac Sim installers, scene assets, model weights, and datasets outside this branch.

## Course baseline and active navigation

The default navigation is now a **single-desk module**, described in
[Desk navigation API](docs/DESK_NAVIGATION_API.md). The main program sends a desk ID;
the module chooses the shortest feasible order of its three inspection poses,
navigates and stops at each, and waits for a correlated work-completion acknowledgement.
The main program owns all outer loops and operations. Localization uses a configured
known starting pose plus measured wheel-velocity integration, with no IMU or AMCL.

Teacher-provided ROS2 originals are preserved under [teacher/ros2](teacher/ros2/README.md),
with source links, archive inventory and SHA-256 checksums. These include the original
Nav2/SLAM YAML files and the Jetson lidar setup script. Packages referenced by the lectures
are listed as dependencies; their source was not included in the supplied scene archive.

The active navigation uses `ic382_navigation`, a profile derived from the teacher baseline
with explicit [team adaptations](docs/NAVIGATION_TEACHER_ALIGNMENT.md), and the new scene-derived
map packaged in `ros2_ws/src/ic382_navigation/maps/inspection/`. The original teacher navigation
parameters remain unchanged; the launcher merges them with the team overrides rather than
launching the original configuration directly.
The existing perception package remains available. The legacy patrol MVP used timed
inspection/tagging placeholders; the new navigation server requires explicit work acknowledgements.

## Getting started

```bash
git clone --depth 1 --single-branch --branch robot-ros2 https://github.com/Ao1Sora/IC382.git IC382-robot
cd IC382-robot
git switch robot-ros2
```

Create your ROS2 packages under `ros2_ws/src/`. Use **Ubuntu 22.04 / ROS2 Humble / Python 3.10**.
Both Python and C++ packages are supported. Declare ROS dependencies in `package.xml`;
list third-party Python dependencies with explicit versions in a requirements file.

```bash
source /opt/ros/humble/setup.bash
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
colcon build --symlink-install
colcon test --return-code-on-test-failure
colcon test-result --verbose
source install/setup.bash
ros2 launch ic382_bringup team.launch.py
```

Register the nodes you want to launch in `ic382_bringup/config/team-nodes.json`.
Nodes use simulation time; see [CONTRIBUTING.md](CONTRIBUTING.md) for an example.

For this workspace, commit and push directly to **robot-ros2**.
GitHub runs ROS2 build and test checks automatically.
Use the dedicated navigation launch described in [Navigation MVP](docs/NAVIGATION_MVP.md)
to run Nav2, the mission sequence, timed inspection/tagging placeholders, and durable logs.
Running ROS2 nodes communicate with the simulator through topics; a GitHub push does not update running nodes automatically.

## Simulation bridge check

Run `bash scripts/check-simulation.sh` from a configured ROS2 terminal.
It checks that /clock, /odom, and /scan messages keep arriving, that scan data contains valid ranges,
and that /cmd_vel has a subscriber. It does not send movement commands or start Isaac Sim.
The report is saved to `results/bridge.json` and includes the tested commit SHA.

The navigation scripts support manual tests in the existing HPC Isaac container and isolated
network namespace. Automatic GPU testing on GitHub pushes is not enabled.
See [Navigation MVP](docs/NAVIGATION_MVP.md) and [Server integration](docs/SERVER_INTEGRATION.md).

- [Contribution guide](CONTRIBUTING.md)
- [ROS2 interface contract](docs/ROS_CONTRACT.md)
