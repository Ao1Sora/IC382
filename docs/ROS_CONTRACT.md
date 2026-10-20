# Isaac Sim / Robot Interface Contract

| Topic | Message type | Direction from robot code |
| --- | --- | --- |
| /clock | rosgraph_msgs/msg/Clock | Subscribe: simulation time |
| /odom | nav_msgs/msg/Odometry | Subscribe: odometry |
| /scan | sensor_msgs/msg/LaserScan | Subscribe: lidar |
| /cmd_vel | geometry_msgs/msg/Twist | Publish: base velocity |

These topics reflect the locally saved course601 environment implementation.
They have not been rechecked on the server during this setup.

Invalid lidar returns may be -1. Accept only finite, positive values within range_min and range_max.
Use the live TF tree to determine coordinate frames; do not infer a frame from a topic name alone.
The camera Image and CameraInfo topic names still need to be confirmed in the running scene.

Use simulation time for robot nodes. If several modules request movement,
route them through a single arbitration or navigation node that publishes the final /cmd_vel.
Do not have multiple modules command the base directly at the same time.
