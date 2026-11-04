# HPC 仿真环境版本核对（2026-11-04）

以下版本通过 SSH 读取 HPC `~/Desktop/IC382` 中的安装文件和 Ubuntu 根文件系统的软件包数据库。插件版本来自各自的 `config/extension.toml`；列出安装版本不代表当前会话中所有插件均已启用。

| 组件 | 安装版本 |
| --- | --- |
| HPC 主机系统 | Rocky Linux 8.10 |
| ROS 根文件系统 | Ubuntu 22.04.5 LTS |
| Isaac Sim | `6.0.1-rc.7+release.42383.32955d8d.gl`（安装目录 `isaacsim-6.0.1` 的 VERSION） |
| ROS 2 Humble ros-base | `0.10.0-1jammy.20260908.101203` |
| Navigation2 / nav2-bringup | `1.1.20-1jammy.20260908.015443` / `1.1.20-1jammy.20260908.021125` |
| SLAM Toolbox | `2.6.10-1jammy.20260908.014627` |
| Isaac ROS 2 Bridge | 5.1.2 |
| Isaac ROS 2 Core | 1.9.4 |
| Isaac ROS 2 Nodes | 1.18.13 |
| Isaac ROS 2 Examples | 1.2.4 |
| Isaac ROS 2 Simulation Control | 1.6.6 |
| Isaac ROS 2 TF Viewer | 2.3.3 |
| Isaac ROS 2 UI Components | 1.6.5 |
| Isaac ROS 2 URDF Importer | 2.3.7 |

服务器另有 CUDA 12.8 编译工具、CUDA 兼容组件和 WebRTC Streaming Client 2.0.0 目录；本次尚未独立核对其构建版本。第三方运行时不在此 Git 快照中，参见 [README](README.md) 的外部运行时说明。此清单尚未证明整个环境可在其他机器上重建。
