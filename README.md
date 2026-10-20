# IC382 Robot ROS2 Workspace

The **robot-ros2** branch is the team's workspace for perception, navigation, mission logic, and interface packages.
The simulation environment is maintained separately on [hpc-isaac-sim-env](https://github.com/Ao1Sora/IC382/tree/hpc-isaac-sim-env).
Keep Isaac Sim installers, scene assets, model weights, and datasets outside this branch.

## Getting started

```bash
git clone --depth 1 --single-branch --branch robot-ros2 https://github.com/Ao1Sora/IC382.git IC382-robot
cd IC382-robot
git switch -c feature/your-module
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
The default manifest is empty. Nodes use simulation time; see [CONTRIBUTING.md](CONTRIBUTING.md) for an example.

Push your feature branch and open a pull request with **base = robot-ros2**.
GitHub runs ROS2 build and test checks automatically.
After merging, the code can be tested with Isaac Sim once server integration is available.
Running ROS2 nodes communicate with the simulator through topics; a GitHub push does not update running nodes automatically.

## Simulation bridge check

Run `bash scripts/check-simulation.sh` from a configured ROS2 terminal.
It checks that /clock, /odom, and /scan messages keep arriving, that scan data contains valid ranges,
and that /cmd_vel has a subscriber. It does not send movement commands or start Isaac Sim.
The report is saved to `results/bridge.json` and includes the tested commit SHA.

**The server runner has not been installed, and automatic GPU testing is not enabled.**
No server changes were made during this setup. The existing HPC runtime uses a container and isolated network namespace;
see [Server integration](docs/SERVER_INTEGRATION.md) for the remaining setup.

- [Contribution guide](CONTRIBUTING.md)
- [ROS2 interface contract](docs/ROS_CONTRACT.md)
