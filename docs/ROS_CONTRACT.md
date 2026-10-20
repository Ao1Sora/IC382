# Isaac Sim / 机器人接口

| 话题 | 类型 | 方向（机器人代码视角） |
| --- | --- | --- |
| /clock | rosgraph_msgs/msg/Clock | 订阅，仿真时间 |
| /odom | nav_msgs/msg/Odometry | 订阅，里程计 |
| /scan | sensor_msgs/msg/LaserScan | 订阅，激光 |
| /cmd_vel | geometry_msgs/msg/Twist | 发布，底盘速度 |

以上对应本地保存的 course601 环境实现；尚未在本次服务器会话中复测。
激光无效回波可能为 -1，必须按 range_min/range_max 且有限正数过滤。
坐标变换以运行时 TF 树为准，不要仅凭话题名推断 frame。
相机 Image / CameraInfo 的具体话题尚待现场确认，不能假设已经启用。

业务节点使用仿真时间。多个模块需要控制底盘时，应由统一仲裁/导航节点发布最终 /cmd_vel。
不要由多个模块同时直接控制机器人。

