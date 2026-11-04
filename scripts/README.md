# scripts 目录

## 运行入口

- `robot_console.py`：主程序，由根目录 `run.sh` 启动。
- `keyboard_bindings.py`、`process_control.py`：按键表和进程生命周期工具，无独立驾驶节点。
- `map_catalog.py`、`map_ui.py`：地图/场景和 RViz 桌面标记。
- `localization_only.launch.py`、`map_preview.launch.py`、`robot_navigation.rviz`：主程序调用的定位和显示配置。
- `reset_robot.py`：由根目录 `reset_robot.sh` 调用，限定机器人进程范围。

## 测试

- `check_navigation.py`：统一测试入口，建议使用 `bash run.sh test`。
- `check_*.py`、`check-desk-api.py`：各功能的回归检查，固定隔离域的检查不得并行运行。
- `check_manual_start.py`：需要实体底盘的启动/退出检查，不在自动套件中。
- `check_inspection_paths.py`：历史点间规划问题的只读复现实验，需要当时场景和实际设备参数，不作为通用回归入口。

## 维护与外部调用

- `preserve_pose_for_reload.py`：维护停车状态下保存/恢复现有定位估计。
- `diagnose_motion.py`、`assess_scan_alignment.py`：运动链与雷达/地图只读诊断。
- `demo-inspect-desk.py`：外部程序调用巡检动作的示例。
- `hpc-*.sh`、`run-course-navigation.sh`、`monitor-isaac-inspection.py`：HPC/Isaac Sim 工具。

旧的 `manual_drive.py` 和 `keyboard_drive.py` 独立驾驶入口已由统一控制台替代。老师原始键盘代码仍在老师源码包中保留，抽出的按键表保留原许可证。
