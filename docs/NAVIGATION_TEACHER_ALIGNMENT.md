# 参考老师导航配置的修改

老师原件：`teacher/ros2/config/custom_nav2_params.yaml`，SHA-256
`fd50817f337a30fac957b49d2fb29a8001496ed1962e2e0ee20a1a244b0a553f`。
本次重新核对 Canvas 当前 Week 06（文件 340582）；讲义第 37 页使用 Nav2 bringup
加载静态地图和参数，第 28 页的固定 TF 数值针对原始 Wheeltec 底盘。

## 参数来源可追溯

运行参数按“老师原始 YAML → nav2_team_overrides.yaml → 本次仿真初始位姿”生成。
`nav2_course.yaml` 是两份 YAML 的静态生成结果，用于直接加载和审核，不再保存旧的硬编码出生位置。
运行时初始化仍只读取一次仿真位姿；导航中使用 AMCL，不持续读取真值定位。
生成器在缓存旁写入 `.sources.json`，记录原件/覆盖文件哈希和这一次初始位姿。

```bash
python3 scripts/configure-course-navigation.py --static \
  --output ros2_ws/src/ic382_navigation/config/nav2_course.yaml
```

## 保留与适配

| 部分 | 修改依据 |
| --- | --- |
| 全局/局部算法 | 保留老师 NavFn、plain DWB、ObstacleFootprint critics 和 BT 恢复流程，不添加 RotationShim |
| 最低转向速度 | 恢复正的 min_speed_xy=0.05；min_speed_theta=0.15 与团队角速度上限 0.3 匹配，避免此前 0 平移下低速转向筛选失效 |
| AMCL 转角更新 | 保留老师 update_min_a=0.2，减少到点旋转时过密的定位修正 |
| 雷达局部避障范围 | 恢复老师局部 marking/clearing 15/20、全局 20/25 场景单位，替代此前过宽的 80/100；AMCL 仍可用 200 的远处墙体回波 |
| 雷达高度 | 使用老师的 -1 到 3 场景单位；当前雷达挂点在 base_link 上方 1.7 场景单位 |
| CAD 轮廓与地图 | 覆盖为团队实测包围轮廓和新地图的 0.25 分辨率，保持地图文件不变；不复制老师原底盘 TF 偏移 |
| 雷达无回波 | 使用 /scan_nav，-1 转为 inf；避障层启用 inf_is_valid，最低距离匹配原 RTX 雷达的 1 |
| 速度/计算负载 | 保留团队 2.0 线速度、0.3 角速度上限和 10 Hz 控制频率，适配 10 倍场景及当前 HPC |
| 到点与停车 | 保留团队位置 0.5、朝向 0.2 容差、失败终止、任务日志及唯一最终速度门控 |

启动前验证器检查最低速度、角速度上限、扫描范围、传感器话题、轮廓一致性和到点容差；不一致时拒绝启动。
新地图仍是几何投影地图，白色不代表真实实测空闲；本次不会把地图替换回旧 my_map。

视觉/贴标继续为定时占位。配置及短程仿真验证不等同于完整多点考核验收。

## 来源

- https://canvas.polyu.edu.hk/courses/3487/files/340582?module_item_id=127069
- https://canvas.polyu.edu.hk/courses/3487/files/286508
- https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/controller_plugins/dwb_controller/dwb_params/kinematic/

Nav2 参数接口以 HPC 实际安装的 Humble 为准；链接中的新发行版示例不直接复制为运行配置。
