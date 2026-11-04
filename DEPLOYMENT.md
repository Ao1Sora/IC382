# 部署 HPC 机器人仿真

此文档以 2026-11-04 的 HPC 状态为基准，面向具备 GPU 的 Linux x86-64 主机。现有启动器是针对 HPC 的 Slurm、Bubblewrap、VNC 和私网设置编写的；不同机器需要适配，不能保证按以下步骤直接得到完全相同的运行结果。

## 已确认的组成

* Isaac Sim 6.0.1，ROS 2 Humble，Ubuntu 22.04 用户空间；[详细版本](HPC-VERSIONS-20261104.md)和 [HPC ROS 包清单](config/hpc-ros-packages-20261104.txt)。
* 机器人代码 `robot-ros2` 分支的提交 `a0ab04797c2fb96e29c9eea2905208355fbf669a`；团队机器人及老师场景保存在本分支中，见下方校验。
* 原服务器 RTX 3080 Ti、驱动 550.54.14、CUDA 编译器 12.8.93；ROS 2 Bridge 等为 Isaac 自带扩展。旧驱动专用兼容层硬编码该驱动和 `sm_86`，不适用于任意 GPU 或驱动。

## 获取项目和模型

安装 Git LFS、Git、Bubblewrap、curl、tar、xz、unzip、gcc、Python 3 及 sha256sum。下载后使用 Linux shell：

```bash
git lfs install
git clone --branch hpc-isaac-sim-env https://github.com/Ao1Sora/IC382.git IC382
cd IC382
git lfs pull
bash scripts/setup-robot-checkout.sh
```

机器人代码固定在上述提交并保留 `robot-ros2` 分支名，启动脚本会检查分支名。`git lfs pull` 必须完成；仅有 LFS 指针不能运行。HPC 上机器人代码 HEAD 与该提交一致；两个机器人 USD 和核心场景 USD 的 SHA-256 与远端 LFS 对象一致，且已实际下载校验。其他场景资源及完整运行行为尚未逐项验证。

## 安装软件

1. 从 [NVIDIA 6.0.1 下载页](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/download.html)取得 Linux x86-64 Isaac Sim 6.0.1 压缩包和 [WebRTC Streaming Client 2.0.0 Debian 包](https://downloads.isaacsim.nvidia.com/isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb)，并自行审阅 NVIDIA 的许可条款。下载页提供两者的校验值。将 Isaac 解压至 `tools/isaacsim-6.0.1/`，确保 `VERSION` 和 `python.sh` 直接位于该目录。根据 NVIDIA 的[安装说明](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/install_workstation.html)完成需要的安装步骤。将客户端 Debian 包用 `dpkg-deb -x <客户端.deb> tools/webrtc-client-2.0.0` 解压，确认实际程序位于 `tools/webrtc-client-2.0.0/opt/Isaac Sim WebRTC Streaming Client/isaacsim-webrtc-streaming-client`。
2. 安装 ROS 用户空间：运行 `bash scripts/setup-ros-root.sh --exact`。该脚本下载并校验 Ubuntu 22.04 官方基础 rootfs，用 Bubblewrap 在项目目录内安装记录的 ROS 包，不改宿主机软件包。它拒绝覆盖已有的 `tools/ros2-humble-root`。
3. **精确版本限制：** HPC 安装的 ROS 包构建日期为 2026-09-08；核对时官方源已提供 2026-09-16 构建，旧版未在当时的本机源索引中列出，HPC 的 apt 缓存也没有旧 deb。因此 `--exact` 可能失败；要精确复现必须提供包含清单中旧版本的可信 apt 快照，或者取得经授权的原始 Ubuntu rootfs 副本。`bash scripts/setup-ros-root.sh --current` 使用当前源的同名包，可能可运行，但并非逐包相同。两种模式都需要在一个**不存在** rootfs 目录的全新检出中执行；失败后保留的目录应由操作者检查处理。
4. 在复现 HPC 旧驱动环境时，从 [NVIDIA CUDA 软件包目录](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/)获取 `cuda-nvcc-12-8_12.8.93-1_amd64.deb`，使用 `dpkg-deb -x <包名> tools/cuda-nvcc-12-8`；确认其中含 `usr/local/cuda-12.8/bin/ptxas` 和 `nvlink`。执行 `bash scripts/build-rtx-cuda-proxy.sh` 编译项目兼容库。该兼容库只针对 HPC 指定驱动和 GPU 验证。
5. 准备配置并编译机器人：

```bash
bash scripts/prepare-runtime-config.sh
bash scripts/week06-ros.sh bash -c 'cd /workspace/robot-ros2/ros2_ws && colcon build --symlink-install'
bash scripts/check-deployment.sh
```

最后的检查只验证关键文件、模型哈希和机器人提交；它不验证所有纹理、GPU 渲染或导航是否正常。

## HPC 上启动与检查

使用已经分配的 GPU 作业及 VNC 桌面，在作业内运行 `./start-course.sh`。启动器绑定了 HPC 私网、显示环境及驱动库路径；其他环境需调整 `scripts/course601-desktop.sh`、`scripts/team-robot-simulation.py` 中的网络设置和容器 GPU 绑定，并根据 GPU 驱动确定是否使用 HPC 专用兼容层。首次运行前核对 NVIDIA 硬件与驱动要求。

启动后在另一终端检查：

```bash
./scripts/week06-ros.sh ros2 topic list
./scripts/week06-ros.sh ros2 topic hz /clock
./scripts/week06-ros.sh ros2 topic hz /scan
./scripts/week06-ros.sh ros2 topic hz /odom
./scripts/week06-ros.sh ros2 node list
```

确认机器人、地图及导航节点正常后，再在安全场景测试移动；系统默认只进入 IDLE。相机识别、贴标机构及完整多点巡航不应仅凭本说明视为已验收。
