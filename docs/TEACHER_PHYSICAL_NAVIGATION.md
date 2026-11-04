# 老师导航底层 + 团队单桌三点巡检

实现依据：2026-10-28 SSH 只读核对 Jetson 10.11.31.13 的已安装 Wheeltec 文件。
车体模式 senior_diff；底盘/EKF 输出 odom_combined；雷达 scan；base_footprint 为车体参考系。
保留预装 AMCL、EKF、Nav2 控制器与规划器。导航入口不再运行团队 wheel_odometry 或固定 map→odom。

团队接口不变：InspectDesk 指定桌号，Nav2 返回路径长度以选择三个点的访问顺序，逐点导航并等待 CompleteInspection 确认。
不启动老师外层 waypoint_cycle，避免与团队动作服务器争用导航目标。

## 准备

统一运行配置位于 `ros2_ws/src/ic382_navigation/config/physical_runtime.yaml`。
复制到运行环境后编辑这一个 YAML，启动只需：

```bash
ros2 launch ic382_navigation navigation.launch.py config_file:=/absolute/path/physical_runtime.yaml
```

相对路径以配置文件所在目录为准。默认 `start_hardware: false`，准备好实机后在配置中改为 true。
inspection.parking_distance_m 默认 0.5，定义为机器人朝桌侧外廓与桌面边缘的净距，不是 base_footprint 原点到桌边的距离。
机器人外廓优先使用配置中的 inspection.robot_footprint，否则继承老师当前车体参数。
inspection.desks 填桌号及实测凸多边形的顶点；程序在每条边中点外侧生成一个面向桌子的候选点，支持每桌 3–8 条边。
自动模式必须提供包含桌面完整投影的 navigation_map。Nav2 从当前位置及候选点之间计算避障路径长度，再在候选点中选三个及其最短访问顺序。
选出的三个点在本次任务中固定，后续每到一点重新规划剩余点顺序；仍由主程序确认作业。
候选点不是相机覆盖认证：本版没有按相机 FOV、距离或遮挡过滤，也未预认证完整原地转向空间；Nav2 的路径/控制碰撞检查仍生效。
没有可行的三点路径时任务失败，不用直线距离强行替代。配置 points 非空时兼容原来的手测三点文件。

在 Jetson 编译本仓库 ros2_ws（source /opt/ros/humble/setup.bash 和 ~/wheeltec_ros2/install/setup.bash 后执行 colcon build）。
按老师 Week 06 流程用 wheeltec_slam_toolbox 建图、wheeltec_nav2 save_map 保存。
结束建图/键盘控制程序后使用下面的入口；不要同时运行 wheeltec_nav2.launch.py 或另一份底盘驱动。

没有正式场地时，不提供虚构的实机巡检坐标。使用临时环境的真实米制地图，测量或用 record_waypoint 记录 T04-A、T04-B、T04-C。
points YAML 必须包含 frame_id: map、scene_scale: 1、calibrated: true，以及每桌恰好三个带 desk_id、id、x、y、yaw 的 waypoints。
calibrated 只能在实际核对坐标、朝向及转弯净空后设置 true。

```bash
source /opt/ros/humble/setup.bash
source ~/wheeltec_ros2/install/setup.bash
source ros2_ws/install/setup.bash
ros2 launch ic382_navigation navigation.launch.py \
  map:=/absolute/path/measured-map.yaml points:=/absolute/path/measured-points.yaml
```

start_hardware:=true 时启动老师的底盘、IMU处理、EKF、雷达与 AMCL/Nav2。start_hardware:=false 用于已启动硬件或隔离的无硬件集成测试。
params_file 默认按当前设备 car_mode 读取已安装的老师参数；不使用十倍场景参数。
在 RViz 通过 2D Pose Estimate 设置实际起点，检查雷达/地图对齐后才能发送桌号。
默认最终速度上限 0.1 m/s、0.3 rad/s。门控订阅 /scan 和 /odom_combined，Nav2 输出重映射到 /ic382/nav2_cmd_vel，仅门控输出最终 /cmd_vel。
不要同时启动键盘、遥控或其他直接发布 /cmd_vel 的程序。此软件门控不替代底盘硬件急停。

```bash
ros2 action send_goal /ic382/inspect_desk ic382_interfaces/action/InspectDesk '{desk_id: T04}' --feedback
```

每次 WAITING_FOR_WORK 后，主程序调用 /ic382/complete_inspection 并提供对应 task_id、point_id、success。
接口及取消、超时说明见 DESK_NAVIGATION_API.md。demo-inspect-desk.py 只是定时模拟作业的主程序示例。

## 低位雷达看不到桌面

两个 costmap 都保留 static_layer，并用 Max 合并雷达层；不能仅靠桌腿扫描保护上层机构。
可传 navigation_map:=/absolute/path/annotated-navigation-map.yaml，加载桌面完整投影和安全边距。
此地图须与 map 参数使用同一物理坐标系；AMCL 仍使用原始雷达地图。
不传 navigation_map 时两个 costmap 使用原始地图；若其中只有桌腿，不能声称已覆盖桌面悬挑。
真实 footprint 继承老师实机配置；加装上层机构后应通过自备 params_file 更新整车外廓。
定位误差、移动的桌子、未知悬空障碍仍需现场验证或增加高度感知。

