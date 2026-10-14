# Week 06 第二部分：服务器实测结果

2026-10-07 已在 PolyU Student HPC 的 GPU 作业 138112（h07g02）完成课程场景的 ROS2 控制、SLAM 建图、地图保存和 Nav2 自主导航。课程材料通过用户提供的 Canvas 链接登录后下载，原始模型和参数文件均保留。

## 已完成与验证

| 项目 | 实测结果 |
| --- | --- |
| ROS2 | Humble；导航、SLAM、RViz、键盘控制包安装完成 |
| 仿真桥接 | `/clock`、`/scan`、`/odom`、TF 和 `/cmd_vel` 通信正常 |
| 速度控制 | 仿真机器人前进约 4.62 米，能够响应转向指令 |
| SLAM | 1206 × 1242 栅格；分辨率 0.05 米；约 107 万个已知栅格 |
| 地图保存 | `dev/map/my_map.pgm` 和 `dev/map/my_map.yaml` |
| AMCL | 初始姿态设置后定位成功 |
| Nav2 | `NavigateToPose` 返回状态 4（成功），实际移动 2.099 米，目标误差 0.401 米，符合课程设置的 0.80 米容差 |
| RViz | 已在 HPC VNC 桌面打开；Navigation 和 Localization 均为 active；地图、激光及代价地图可见 |

这些距离属于课程中放大 10 倍的仿真模型，不是实物机器人的行驶记录。当前保存的是机器人附近的局部场景地图，尚未覆盖整栋建筑。

## 现在如何继续

打开本地 [Connect-Gui.cmd](D:/ChatGPT/IC382/hpc/Connect-Gui.cmd) 进入服务器桌面。RViz 已经打开，可以用工具栏的 **Nav2 Goal** 设置新的目标。桌面新增了 `IC382 Week06 navigation`、`mapping` 和 `keyboard` 三个入口。

服务器工程目录是 `~/Desktop/IC382`。在服务器终端执行：

```bash
cd ~/Desktop/IC382
./scripts/week06-session.sh status
./scripts/week06-session.sh navigation
```

重新建图时，分别在两个终端执行：

```bash
./scripts/week06-session.sh mapping
./scripts/week06-session.sh keyboard
```

键盘控制使用 `i` 前进、`j/l` 转向、`k` 停止。完成建图后执行：

```bash
./scripts/week06-session.sh save-map
./scripts/week06-session.sh navigation
```

如果重新建图后改变了地图坐标，应在 RViz 使用 **2D Pose Estimate** 重新设置当前位置。自动初始化保存的是本次已验证地图的坐标关系。

```bash
./scripts/week06-session.sh stop
```

上述 stop 只停止 Week 06 会话。当前 GPU 作业在北京时间 **2026-10-07 20:17:28** 到期；当前仿真进程最长运行两小时，约 20:04 结束。作业结束后通过已有连接入口重新申请 GPU，再运行 navigation 即可继续。

## 服务器适配说明

服务器安装的是 Isaac Sim 4.5，课件按较新版本编写。已生成单独的兼容场景、重建 ROS2 控制图和 RTX 激光，补充轮子的圆柱碰撞体并调整驱动增益。仿真目前以后台模式运行；HPC 桌面显示 RViz，Isaac 场景有单独截图。

ROS2 在工程内独立的 Ubuntu 22.04 环境运行，解决服务器 Rocky Linux 的 glibc 与 ROS bridge 不兼容问题。未改动服务器系统或 NVIDIA 驱动。

激光适配节点将 Isaac 4.5 的无回波值 `-1` 表示为量程边界，SLAM 在该边界只标记自由空间，不生成障碍物终点；原始 `/scan` 保留，建图和导航使用 `/scan_corrected`。处理依据已核对 [SLAM Toolbox Humble 的栅格射线代码](https://raw.githubusercontent.com/SteveMacenski/slam_toolbox/humble/lib/karto_sdk/include/karto_sdk/Karto.h)。参数改动保存在 `custom_slam_params_hpc.yaml` 和 `custom_nav2_params_hpc.yaml`。

## 验证材料与来源

- [Nav2 实测结果 JSON](D:/ChatGPT/IC382/hpc/week06/logs/week06-navigation-result.json)
- [最终地图](D:/ChatGPT/IC382/hpc/week06-map.png)
- [RViz 画面](D:/ChatGPT/IC382/hpc/week06-rviz-window.png)
- [Isaac 课程场景截图](D:/ChatGPT/IC382/hpc/week06-scene.png)
- [服务器脚本与地图备份](D:/ChatGPT/IC382/hpc/week06-results.tar.gz)
- [Week 06 课件，第 20–38 页](<C:/Users/gyt20/Downloads/10 - IC382 - Stage 1 - Week 06 - ROS2 Robot Control and Isaac Sim.pdf>)
- [Canvas 课程材料下载](https://canvas.polyu.edu.hk/courses/3487/files/286508/download?download_frd=1)，本次已实际下载并使用。

本次也实时检查了在线 IC382 项目 Sources 和相关分工聊天；实验步骤依据上述课件与 Canvas 包。`chatgpt-sync` 是较旧的本地快照，本次不把它作为当前服务器配置的依据。
