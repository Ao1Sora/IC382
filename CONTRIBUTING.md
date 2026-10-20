# Contributing robot code

1. Create your feature branch from `robot-ros2`.
2. Put ROS2 packages under `ros2_ws/src/`. Suggested names include `ic382_perception`,
   `ic382_navigation`, `ic382_mission`, and `ic382_interfaces`; create them as needed.
3. Declare dependencies in `package.xml`. Keep build/install/log directories, datasets, models,
   installers, keys, and passwords out of Git.
4. Build and run your package tests, push your branch, and open a pull request with **base = robot-ros2**.
5. Describe the input/output topics, launch command, and test evidence in the PR. Merge after the checks pass.

Maintain the simulation environment and robot code separately.
Do not merge the entire robot branch into the simulation environment branch.
The server should build a separate checkout of this workspace and connect it through the ROS2 bridge.

## Registering nodes

Edit `ros2_ws/src/ic382_bringup/config/team-nodes.json`:

```json
{
  "nodes": [
    {
      "name": "mission",
      "package": "ic382_mission",
      "executable": "mission_node",
      "enabled": true,
      "arguments": []
    }
  ]
}
```

This example requires you to create and install the corresponding package and executable.
No mission, perception, or navigation implementation is included by default.

Launch the configured nodes:

```bash
ros2 launch ic382_bringup team.launch.py
```

To use a custom manifest:

```bash
ros2 launch ic382_bringup team.launch.py config:=/absolute/path/nodes.json
```

Nodes use `use_sim_time=true`. Only one final controller should publish to /cmd_vel.
Write tests for your module's actual behavior. The bridge check verifies basic communication;
it does not establish that a robot mission succeeds.
