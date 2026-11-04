# 测试入口

Jetson 已构建并安装依赖后，在工程根目录运行：

```bash
bash run.sh test --suite unit
bash run.sh test                  # 默认 quick
bash run.sh test --suite full
```

所有测试子进程固定使用 ROS_DOMAIN_ID=138，并串行运行；不启动真实底盘。必须避免其他维护终端同时在该测试域运行旧的独立检查脚本。

- `unit`：Python 单元测试。HPC 场景资源相关的 `test_simulation_profile.py` 不在实机回归范围。
- `quick`：单元测试，加统一键盘 PTY 检查、控制台任务分派、点导航门控、定位辅助、地图绑定/标记、重置范围、局部匹配、回调负载和三点巡检接口。
- `full`：追加真实 C++ 控制/规划插件和 Nav2 恢复行为的隔离检查；使用合成地图与模拟后端。

测试结果默认写入 `~/.local/state/ic382/test-results/<时间>/`，包含 `summary.json` 和各项日志。可用 `--output /tmp/my-check-results` 指定位置。测试控制台日志使用临时目录，与实车任务日志隔离。

`check-desk-api.py` 明确验证：未按 C 前不提交后续目标、停车位姿变化后更新下一目标、等待超过 5 秒后按 C 可继续、真实缺失日志 ACK 仍超时失败。

`check_manual_start.py` 是单独的实体底盘启动检查，**不在上述套件内**。实车移动、定位对齐、地图质量和三点实际停车误差仍由实机验收确认。
