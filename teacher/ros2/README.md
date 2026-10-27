# 老师提供的 ROS2 基础资料

2026-10-22 实时核对 Canvas 课程 Modules；本目录原件保存老师实际提供的配置和脚本，供团队在其基础上开发。

| 原件 | 来源 | 用途 |
| --- | --- | --- |
| config/custom_nav2_params.yaml | Canvas 文件 286508 的 ROS2 Isaac_Sim Materials.zip | 老师原始 Nav2 参数 |
| config/custom_slam_params.yaml | 同一原始 ZIP | 老师原始 SLAM Toolbox 参数 |
| scripts/setup_new_wheeltec_lidar.sh | 本次登录 Canvas 后下载文件 286509 | Jetson 物理雷达串口的 udev 配置 |

两份 YAML 与 HPC 保存的原始 ZIP 条目逐字节核对；雷达脚本本次下载原件未修改。
`provenance.json` 记录来源、字节数与 SHA-256；`archive-inventory.json` 保留原始 ZIP 的 517 个文件条目。
本次未重新下载 1.52 GB ZIP，核验的是现有 HPC 原包及当前课程入口。

来源：
- https://canvas.polyu.edu.hk/courses/3487/modules
- https://canvas.polyu.edu.hk/courses/3487/files/286508
- https://canvas.polyu.edu.hk/courses/3487/files/286509
- 当前 Week 06：https://canvas.polyu.edu.hk/courses/3487/modules/items/127069
- 当前 Week 04：https://canvas.polyu.edu.hk/courses/3487/modules/items/127068

## 课程包与已有软件依赖

原始 ZIP 包含 USD 模型、纹理、收集元数据和上述两份 YAML，没有独立 ROS 包源码树。
讲义启动的下列程序来自 ROS2 或 Wheeltec/Jetson 预装环境；源码未随这个 ZIP 提供：

| 环境 | 讲义引用的软件包 |
| --- | --- |
| Jetson 相机 | astra_camera、rqt_image_view、web_video_server |
| Jetson 底盘 | turn_on_wheeltec_robot、wheeltec_robot_keyboard |
| Jetson SLAM/导航 | wheeltec_slam_toolbox、wheeltec_nav2、wheeltec_rviz2 |
| 仿真/PC | teleop_twist_keyboard、slam_toolbox、nav2_bringup、nav2_map_server、tf2_ros |

没有把自行编写的 week06-* HPC 适配脚本当作老师源码。本分支不复制大体积三维场景；场景保存在仿真环境分支。
雷达脚本用于物理 Jetson 的设备规则，保留原件但不在 HPC 或仿真启动时执行。

## 团队默认运行方式

默认使用团队 `ic382_navigation` 单桌导航接口、由老师基线合并生成的团队参数，
以及 `maps/inspection/scene_map.yaml`。主程序指定桌号，在每个停车点执行作业并确认；
演示主程序用定时等待占位，不启动物理机构。见 [当前接口](../../docs/DESK_NAVIGATION_API.md)。
课程包未提供实体底盘驱动源码，尚未核验 Jetson 是否公开独立左右轮速；不能从仿真接口推断实机能力。
