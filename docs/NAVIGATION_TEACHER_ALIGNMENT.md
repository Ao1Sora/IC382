# 老师基线与当前团队导航配置

老师原始文件保留在 `teacher/ros2/config/custom_nav2_params.yaml`，SHA-256：
`fd50817f337a30fac957b49d2fb29a8001496ed1962e2e0ee20a1a244b0a553f`。
运行参数由这份原件与 `config/nav2_team_overrides.yaml` 合并生成，原件不修改。
当前入口使用 `--static` 生成参数；不读取 Isaac 绝对位姿初始化导航。

当前运行方式见 [单桌导航接口](DESK_NAVIGATION_API.md)。原有 AMCL 巡检 MVP
仍保留作参考，但不由默认启动脚本启动。

| 部分 | 当前行为与原因 |
| --- | --- |
| 全局规划 | 保留老师的 NavFn；比较其返回的障碍感知路径长度，选择三个点的最短访问顺序 |
| 路径跟踪 | 保留 DWB 和 ObstacleFootprint critics，外包 Nav2 官方 Rotation Shim；先原地对齐行进方向，避免离开桌边时正反转振荡 |
| 到点转向 | Rotation Shim 对齐桌面方向，速度上限 0.5 rad/s；整车角速度上限仍为 0.6 rad/s |
| 静态避障 | 全局和局部均启用 static_layer；低位雷达看不到桌面悬挑，局部控制器必须保留二维地图里的桌面区域 |
| 安全余量 | 完整 CAD 轮廓加 0.75 场景单位边距；膨胀半径 8.0、衰减系数 0.3，适配十倍场景并避免贴桌角行走 |
| 地图 | 使用 `maps/inspection/scene_map.yaml`，包含保守的桌椅包围范围，不切回老师的旧 my_map |
| 定位 | 已知起点固定 map→odom；默认累计轮子转角，只有轮速时退回速度积分；不启动 IMU、AMCL 或 SLAM |
| 雷达 | `/scan_nav` 用于动态避障；保留 -1 到 3 的高度范围、无回波转 inf、marking/clearing 距离和范围一致性检查 |
| 速度 | 线速度上限 3.5 场景单位/s，即实际 0.35 m/s；控制频率 10 Hz |
| 停车与作业 | 到点容差 0.5 场景单位、0.2 rad；停车后等待主程序确认，保持独立速度门控与持久日志 |

这里的轮子反馈由 Isaac 提供。实体 Jetson 是否公开左右独立轮速，尚未验证；
课程包不含 `turn_on_wheeltec_robot` 驱动源码。实机应先检查驱动和 `/odom`，
不能把仿真的 `/joint_states` 当作实体底盘已具备的接口。

启动前验证器检查 DWB 主控制器、转向上限、静态地图层、扫描范围、轮廓和到点容差。
物理接触配置与软件里程计的实测限制见接口文档；单元测试不等于完整实机验收。

来源：

- [Canvas Week 06](https://canvas.polyu.edu.hk/courses/3487/modules/items/127069)
- [课程原始材料](https://canvas.polyu.edu.hk/courses/3487/files/286508)
- [Nav2 Humble Rotation Shim](https://github.com/ros-navigation/navigation2/tree/humble/nav2_rotation_shim_controller)
- [Nav2 静态地图层](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/costmap_2d/costmap_plugins/static/)

参数以 HPC 实际安装的 ROS2 Humble 为准；新发行版的嵌套命名空间配置未直接套用。