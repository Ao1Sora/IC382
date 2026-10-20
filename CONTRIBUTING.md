# 提交机器人代码

1. 从 codex/robot-ros2 创建自己的 feature 分支。
2. 包放在 ros2_ws/src/ 下，建议命名 ic382_perception、ic382_navigation、ic382_mission、ic382_interfaces，按实际需要创建。
3. package.xml 声明依赖。不要提交 build/install/log、数据集、模型、安装程序、密钥或账号密码。
4. 编译并运行包自己的测试，再 push 创建 PR，base 明确选择 codex/robot-ros2。
5. PR 描述输入/输出话题、启动命令和测试证据。通过检查后再合并。

仿真环境分支与机器人分支分别维护。不要把机器人分支整体合并到仿真环境分支；
服务器应把机器人代码作为独立 checkout 构建，再通过 ROS2 bridge 联调。

## 登记启动节点

编辑 ros2_ws/src/ic382_bringup/config/team-nodes.json：

```json
{
  "nodes": [
    {
      "name": "mission",
      "package": "ic382_mission",
      "executable": "mission_node",
      "enabled": true,
      "arguments": []
    }
  ]
}
```

上例需要你实际创建并安装对应 package/executable；默认不包含这些业务节点。
统一启动命令：ros2 launch ic382_bringup team.launch.py。
自定义清单：ros2 launch ic382_bringup team.launch.py config:=/absolute/path/nodes.json。
统一使用 use_sim_time=true；只允许一个最终控制节点发布 /cmd_vel。
业务测试应覆盖自己的算法行为；桥接检查只证明通信基本连通，不能代替任务完成测试。

