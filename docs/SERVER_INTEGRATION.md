# 服务器后续接入

状态：代码已准备；服务器未修改，GPU runner 未安装、未启用。

先恢复 HPC 访问并满足 ITS 的磁盘要求，再安排接入。已有 Isaac Sim 场景和安装目录保留独立，
机器人代码按 README 用 depth=1 单分支克隆到另一个目录，避免拉取大量历史仿真资产。

## 手动联调

1. 按仿真环境分支的流程申请 GPU 并启动课程场景，确认 bridge 和 Play 正常。
2. 进入与 Isaac Sim **相同的 ROS2 网络/用户命名空间**；现有 course601 使用隔离命名空间，
   仅设置 ROS_DOMAIN_ID 并不足够。需为独立机器人 checkout 增加容器绑定目录。
3. 在其中 source ROS2 Humble，构建机器人工作空间，source install/setup.bash。
4. 执行 bash scripts/check-simulation.sh，查看报告中的提交 SHA、消息计数和结果。
5. 启动 team.launch.py 运行队友节点，并单独记录任务完成情况。

现有 HPC 的 Ubuntu 根目录容器只绑定了仿真项目；本分支不提供未经验证的自动 nsenter/bwrap 命令。
不要在宿主机直接 source 容器内的 /opt/ros/humble。此适配需在服务器恢复后验证。

## 未来自动联调

GitHub 的 ROS2 CI 已与 GPU 分离。后续在 GPU 分配有效、网络命名空间和挂载已验证的环境中注册专用 runner，
先检出指定提交、运行 CPU 检查，再串行执行构建、桥接检查及任务测试，上传带 SHA 的结果。
仅让可信合并提交进入共享 GPU 队列，并避免两个任务同时控制同一场景。
目前没有配置会挂起等待服务器的 GPU workflow，也不会因提交自动修改现有仿真运行时。

