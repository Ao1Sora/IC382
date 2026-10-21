# 初版仿真验证记录 — 2026-10-21

版本状态：可审核 MVP，完整四点两轮巡航仍在 HPC 测试，尚未验收。

## 已验证

- 在既有 HPC GPU 作业 139346、Isaac Sim 6.0.1、ROS2 Humble 环境中执行。
- `colcon build --packages-select ic382_navigation ic382_bringup --symlink-install` 成功。
- `colcon test --packages-select ic382_navigation --return-code-on-test-failure` 成功：18 tests，0 errors，0 failures，0 skipped。
- 单点真实移动测试成功：任务 `3ea3ea0f632942deade8392c7d69d06b`，55.59 秒墙钟时间。
- 目标与独立仿真位置误差 0.4534 场景单位；按场景 10 倍比例约为实物 4.53 cm。
- 识别占位与标签占位各停留 3 秒；监测到停留阶段非零速度命令 0 次。
- 终态 COMPLETED，journal_confirmed=true，最终 /cmd_vel=[0,0]。
- 当前单套导航的 /cmd_vel 发布者为 velocity_gate。

原始成功记录在交付压缩包 `evidence/smoke-result.json`，地图对齐诊断为 `evidence/map-alignment.json`。
地图对齐诊断读取独立仿真真值，只作评估，不向 AMCL 或控制器回传。

## 实测后修复

1. 启动前检查 bt_navigator lifecycle=ACTIVE，避免服务发现早于节点激活而拒绝目标。
2. 按实际 ROS 进程组关闭任务，清理 launch 父进程退出后仍存活的组件。
3. 启动时拒绝已运行的旧课程 Nav2 和残留 nav2_container，避免重名服务和双重控制。
4. 每次仿真启动仅用当前真值初始化 AMCL 一次；随后由雷达、里程计和 AMCL 定位。
5. 监测器绑定本次 IDLE 任务 run_id，并要求实际到点数，避免上一轮终态产生误报。

## 尚未完成的验证

四个演示点、两轮共八次到点；取消和断流的实景故障注入；真实机器人测试。
当前多点结果不能作为通过证据。失败的启动调试不计为成功任务。

四个演示点取自老师场景桌边；不是最终考核桌号。识别和贴标签仅为停留占位，
不会产生真实分类、占用判断、标签动作，也没有完成 fair-chance 规则判断。

## 资料依据

本次已实时核对 Canvas 第 6 周讲义入口：
https://canvas.polyu.edu.hk/courses/3487/modules/items/127069

本次实时核对 IC382 在线 Sources，当前列出 Rulebook V2.4；并查阅软件协作聊天：
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/project?tab=sources
https://chatgpt.com/g/g-p-6a97d97945a48191821db914294c8a89-ic382/c/6abcd66a-97e8-83ee-8775-73cdde44180b

本地 `chatgpt-sync/ros2-transcript.md` 是辅助快照，不等同实时资料。
