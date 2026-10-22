# 导航、主程序与日志 MVP

本实现复用 ROS2 Humble 的 Nav2（AMCL、NavFn、DWB、costmap、恢复行为）和
SLAM Toolbox。我们编写任务编排、导航 Action 客户端、速度门控、日志及场景适配。
识别和贴标签是 3 秒停留占位，日志明确写入 `simulated: true`；没有真实识别或标签动作。

上游参考：
- https://github.com/ros-navigation/navigation2/tree/humble
- https://github.com/SteveMacenski/slam_toolbox/tree/humble
- https://api.nav2.org/actions/humble/navigatetopose.html

## 结构

`mission_node` 负责顺序、轮次与停留；`navigation.Navigator` 通过
`nav2_msgs/action/NavigateToPose` 请求 Nav2，并检查成功、拒绝、取消和超时。
`journal` 把 `/ic382/events` 保存为每个 run_id 独立的 JSONL，落盘后发回确认。
`velocity_gate` 是这个 launch 中唯一的最终 `/cmd_vel` 发布者：
Nav2 输出重映射到 `/nav2_cmd_vel`，门控只在导航中且命令/雷达/里程计/任务心跳
持续到达时放行；停留、完成、异常、任务节点退出时输出零。
任务启动还要求 bt_navigator 的 lifecycle 状态为 ACTIVE，避免接口发现早于激活时目标被拒绝。

两轮模式：第一轮每个目标点执行识别停留；第二轮执行识别停留和标签停留。
这是任务衔接示例，不声称完成 occupied/reserved 判断或 fair-chance 合规验证。

## 在普通 Ubuntu 22.04 / Humble 中

安装依赖并在 `ros2_ws` 执行 colcon build，source install/setup.bash。
导航包不启动 Isaac，不启动现有视觉节点，也不改变 team-nodes.json。
先启动自己的机器人/仿真，使 `/scan`、`/odom` 和 TF 正常发布。

```bash
ros2 launch ic382_navigation patrol.launch.py \
  map:=/absolute/path/scene_map.yaml \
  params_file:=/absolute/path/nav2_params.yaml \
  route:=/absolute/path/route.yaml \
  log_directory:=/absolute/path/results/journal
```

默认不自动运动。AMCL 定位确认后：

```bash
ros2 service call /ic382/start_mission std_srvs/srv/Trigger '{}'
ros2 service call /ic382/cancel_mission std_srvs/srv/Trigger '{}'
ros2 topic echo /ic382/mission_status
```

使用 RViz 的 2D Pose Estimate 设置初始位置，或者在经核对的 Nav2 参数中设置
`amcl.set_initial_pose` / `initial_pose`。课程适配脚本只用仿真真值初始化一次；
运行中的定位由 AMCL 完成。独立监测器读取仿真真值用于评估，不向定位或控制回传。

## 二维地图和目标点

现有 scene_map.pgm + scene_map.yaml 由老师场景几何导出，覆盖整个场景房间。
原始老师场景为 10 倍尺寸；地图分辨率 0.25 场景单位等价于实物 0.025 m。
必须在同一套场景坐标下设置 AMCL、速度、footprint 和目标点。
不要把这套 10 倍参数部署到实体机器人。

`config/route.example.yaml` 默认 calibrated=false，不能直接启动。
把机器人停在已验证的桌边后可记录目标：

```bash
ros2 run ic382_navigation record_waypoint --id DESK_A \
  --route /absolute/path/route.yaml --ros-args -p use_sim_time:=true
```

记录器保留 calibrated=false；核对地图、朝向、碰撞余量和目标可达性后再明确设为 true。
目标点必须代表底盘停车位置，而不是桌面中心。演示路线不等同于最终考核桌号。

需要重新用雷达建图时，使用 `mapping.launch.py params_file:=...`，其中 SLAM 的
scan_topic 应设置为 /scan_nav。建图与固定地图 AMCL 导航分开运行。

## HPC

代码置于 `~/Desktop/IC382/robot-ros2`，通过既有 /workspace 挂载访问，
与 Isaac 安装、场景和环境分支分开保存。`scripts/hpc-ros.sh` 会进入当前
course601 的同一个网络命名空间和既有 ROS2 Ubuntu 容器：

```bash
cd ~/Desktop/IC382
./robot-ros2/scripts/hpc-patrol.sh start
./robot-ros2/scripts/hpc-ros.sh bash -c \
  'source /workspace/robot-ros2/ros2_ws/install/setup.bash; ros2 service call /ic382/start_mission std_srvs/srv/Trigger "{}"'
./robot-ros2/scripts/hpc-ros.sh bash -c \
  'source /workspace/robot-ros2/ros2_ws/install/setup.bash; ros2 topic echo /ic382/mission_status'
```

`hpc-patrol.sh start` 使用当前场景位置生成 AMCL 初始位姿，再启动导航；运行后没有真值定位回传。
`hpc-patrol.sh stop` 停止这一套 MVP 的进程组，保留 Isaac 桌面。需要新任务时先 stop 再 start。
该脚本依赖环境中的既有 GPU 作业、course601 桌面、二维地图和 Ubuntu ROS2 容器。

默认仿真桌面通过环境分支的 scripts/start-robot-navigation.sh 加载项目内的 robot-ros2 本地 Git 仓库。启动会打印分支和提交号，不自动 git pull，也不自动运动。手动 hpc-patrol.sh start 仅用于尚未运行导航时；同一场景只启动一套。

## 测试与证据

单元测试覆盖两轮访问顺序、停留时长、失败不进入识别/贴标、取消、重复或非法目标、
传感器断流、限速，以及取消请求发生在目标接受之前的竞态。
HPC build/test 使用真实 ROS2 Humble 库；真实移动另以 monitor-patrol.py 验证。
纯状态机测试不能替代 Isaac 中的移动测试。

监测器记录每个到点事件的 Nav2 结果、AMCL 与独立场景位置、停留阶段的零速度检查、
最终任务状态和日志确认。测试结果见 [初版验证记录](TESTING_INITIAL.md)。完整多点任务尚未验收。

## 现在没有做的部分

真实桌面识别、物品分类、机构电气控制、最终桌位/考核场地标定、真实机器人测试。
速度门控和软件取消不替代硬件急停。
