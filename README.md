# IC382 机器人 ROS2 代码

独立协作分支：**codex/robot-ros2**，用于感知、导航、任务决策和接口包。
仿真环境仍在 [hpc-isaac-sim-env](https://github.com/Ao1Sora/IC382/tree/hpc-isaac-sim-env)。
本分支不存 Isaac Sim 安装程序、场景资产、模型权重或数据集。

## 队友开始开发

```bash
git clone --depth 1 --single-branch --branch codex/robot-ros2 https://github.com/Ao1Sora/IC382.git IC382-robot
cd IC382-robot
git switch -c feature/your-module
```

在 ros2_ws/src/ 新建自己的 ROS2 package。统一使用 **Ubuntu 22.04 / ROS2 Humble / Python 3.10**。
Python、C++ 包均可；依赖写入 package.xml，Python 第三方依赖另写明确版本的 requirements 文件。

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

在 ic382_bringup/config/team-nodes.json 登记要启动的节点，默认清单为空。
节点使用仿真时间；例子见 CONTRIBUTING.md。

提交后创建 **base = codex/robot-ros2** 的 Pull Request。GitHub 自动检查 ROS2 编译及测试。
合并到机器人分支后，后续可交给服务器的 Isaac Sim 联调；ROS2 节点运行期间通过话题实时交互。
GitHub 提交本身不会自动同步到正在运行的节点。

## 仿真测试入口

bash scripts/check-simulation.sh 在已配置好的 ROS2 终端检查 /clock、/odom、/scan 是否持续到达、
激光数据是否有效，以及 /cmd_vel 是否有订阅者。它不发送运动指令，不启动 Isaac Sim。
报告写入 results/bridge.json，包含测试提交号。

目前只完成代码侧准备；**尚未安装服务器 runner，也未启用 GPU 自动测试**。本次未修改服务器。
HPC 现有运行时使用特殊容器/网络命名空间，接入要求见 [服务器接入说明](docs/SERVER_INTEGRATION.md)。

- [贡献流程](CONTRIBUTING.md)
- [ROS2 接口约定](docs/ROS_CONTRACT.md)

