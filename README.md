# IC382 HPC 仿真环境

当前版本：**Isaac Sim 6.0.1 + ROS2 Humble + 原始 RTX OmniLidar + 团队 CAD 机器人**。
本分支 `hpc-isaac-sim-env` 保存 2026-10-21 从 HPC 实际运行目录导出的环境文件。
机器人导航、视觉和任务代码在独立的 `robot-ros2` 分支维护。

## 在现有 HPC 环境启动

```bash
cd ~/Desktop/IC382
./scripts/prepare-runtime-config.sh
./start-course.sh
```

需要已分配的 `ic382-ssh-dev` GPU 作业和 VNC 桌面。流媒体客户端连接私有网络
`10.238.38.1`。关闭客户端会清理该桌面会话启动的进程。
`./demo.sh` 会发送演示运动指令，只能在没有其他底盘控制器运行时使用。

当前桌面入口仍启动课程 Nav2；运行团队导航 MVP 前需要停止已核对的课程 Nav2
进程组，避免两套导航控制同一场景。团队导航启动方法见 `robot-ros2` 分支。

## 必需的外部运行时

以下安装目录位于现有 HPC 项目中，体积大且为第三方软件，不提交 Git：

- `tools/isaacsim-6.0.1/`：Isaac Sim 6.0.1 standalone Linux。
- `tools/ros2-humble-root/`：Ubuntu 22.04 根文件系统，含 ROS2 Humble、Nav2、SLAM Toolbox、ROS Python 依赖和客户端依赖。
- `tools/webrtc-client-2.0.0/`：Isaac Sim WebRTC Streaming Client 2.0.0。
- `tools/cuda-nvcc-12-8/`：NVIDIA CUDA 12.8 ptxas / nvlink。
- `tools/rtx-cuda-proxy.so`：由本分支 C/汇编源码构建的项目局部兼容库。

重建兼容库：`./scripts/build-rtx-cuda-proxy.sh`。
本分支是当前环境源码与资产快照，不包含 Ubuntu 根文件系统或完整离线软件镜像。
不要在 HPC 登录节点运行 Isaac，也不要把容器 ROS 库直接 source 到 Rocky 主机。

## 文件布局

- `scripts/course601-desktop.sh`：当前桌面、仿真、ROS2、客户端启动入口。
- `scripts/team-robot-simulation.py`、`team-robot-loader.py`：CAD 机器人和 ROS2 桥接。
- `scripts/isaac601-*-rtx.sh`、`rtx-cuda-*`：当前 Ubuntu/RTX 兼容链。
- `scripts/week06-*.sh/py`：当前入口仍直接依赖的 ROS、雷达适配和课程导航组件；保留这些名称以保持现有路径兼容。
- `robots/team_robot_20261013/`：真实尺寸及场景 10 倍尺寸的团队 USD。
- `dev/Collected_final_wheeltec_with_scene/`：运行中的 cleaned 场景、原始雷达定义及其收集材质。
- `dev/map/` 和 `dev/custom_*`：课程默认导航地图与参数。
- `output/maps/teacher-scene-20261021/`：由老师场景导出的二维几何地图。
- `environment-manifest.json`：HPC 文件来源、大小、SHA-256 和 Git blob 校验值。

USD 大文件和部分大纹理由 Git LFS 管理。克隆后执行 `git lfs pull`。
旧 4.5 启动器、旧机器人副本、重复场景 USD、试验替代传感器和历史修复脚本已从当前分支文件树移除。
日志、缓存、trace、密码和连接凭据不属于提交内容。

## 已验证与限制

当前运行的主机为 Rocky Linux 8.10、RTX 3080 Ti、NVIDIA 550.54.14。
项目局部 CUDA 兼容层使 Isaac 6.0.1 原始 GPU 雷达在此主机工作；未修改系统驱动。
该兼容方案针对当前 GPU/驱动，不能视为其他硬件上的验证结果。

CAD 机器人实际运动、clock/odom/scan 增长以及单点 Nav2 移动已验证。
完整多点巡航尚未验收；相机只有挂点，未实现真实 ROS 图像识别；升降/贴标机构尚未控制。
原始收集场景仍存在部分缺失纹理引用，几何和控制采用当前已运行版本。
场景保持老师原始 10 倍比例，不能直接使用这些坐标或速度部署到实体机器人。

## 来源

本次主依据：HPC `~/Desktop/IC382` 的当前文件和校验清单。
已实时核对在线 IC382 Sources（Rulebook V2.4）：
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/project?tab=sources

课程原始资料入口：https://canvas.polyu.edu.hk/courses/3487
Isaac 安装包官方地址：https://downloads.isaacsim.nvidia.com/isaac-sim-standalone-6.0.1-linux-x86_64.zip
CUDA 工具官方来源：https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/
