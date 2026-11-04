# IC382 机器人导航

本工程的实机入口是 `bash run.sh console`。统一控制台负责键盘、地图选择、建图、定位和导航任务；ROS 节点负责定位修正、逐点巡检、速度门控和日志，C++ 插件负责车体规划与到点转向。

- 操作机器人：[完整操作手册](docs/ROBOT_OPERATOR_MANUAL_ZH.md)
- 阅读代码：[代码结构与启动链路](docs/CODE_STRUCTURE_ZH.md)
- 验证修改：[测试说明](docs/TESTING_ZH.md)
- 脚本用途：[scripts 目录说明](scripts/README.md)

## 当前目录

```text
run.sh / reset_robot.sh           实机启动与停止入口
scripts/                         控制台、地图界面、维护工具和集成检查
ros2_ws/src/ic382_navigation/     Python ROS 节点、配置、launch 与行为树
ros2_ws/src/ic382_planners/       C++ 车体规划和分阶段转向控制器
ros2_ws/src/ic382_interfaces/     巡检动作与作业确认服务
ros2_ws/src/teacher/              老师/Wheeltec 源码，保留许可证与来源
maps/                            机器人上的地图、禁行区、桌面标定和场景配置
simulation/                      本地 HPC/Isaac Sim 入口与配置
teacher/                         上游源码快照和来源记录
```

`ros2_ws/build`、`ros2_ws/install` 是机器人当前运行所依赖的构建与安装目录，不能把它们当作普通临时文件删除。底层 ROS Humble 和 `/home/wheeltec/wheeltec_ros2` 仍由设备环境提供。地图数据主要保存在机器人端，本地源码仓库不一定含有它们。

## 运行

在 Jetson、已构建的工程目录中：

```bash
bash run.sh console
bash run.sh test                 # 隔离 ROS 域的软件回归，不启动实体底盘
bash run.sh test --suite full    # 追加控制器、规划器、恢复行为的隔离检查
```

`manual`、`drive` 都是统一控制台的兼容别名。老师的独立遥控入口仍为 `bash run.sh teleop`；使用独立入口前先退出控制台。构建入口是 `bash run.sh build`。

P 键只提交当前巡检点。到点停稳、完成实际作业并按 C 后，才从最新位姿选择最近的未巡检候选点并导航，共完成三个不同点。检查点的目标距离为**雷达中心到桌边 0.40 m**。初次定位由操作员完成，之后小范围雷达匹配持续修正；具体限速、容差和取消规则见操作手册。

## 保存与依赖

地图及标定随各自 `maps/<场景>/scene.yaml` 绑定；当前选择保存在 `physical_runtime.yaml`，只保留一份 `.previous` 上一配置。实车任务日志在 `~/.local/state/ic382/`，统一测试结果在该目录的 `test-results/`，测试控制台不写入实车取消日志。

用户确认的基线备份独立于工作目录，不由构建或清理脚本覆盖。整理代码和隔离测试通过，不等于实车巡检验收。HPC 仿真说明见 [simulation/README.md](simulation/README.md)；老师和上游代码来源见 [teacher/README.md](teacher/README.md)。
