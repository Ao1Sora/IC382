# 文档入口

以下文档描述当前代码：

- [机器人操作手册](ROBOT_OPERATOR_MANUAL_ZH.md)：操作步骤和当前参数。
- [代码结构](CODE_STRUCTURE_ZH.md)：入口、节点和模块职责。
- [测试说明](TESTING_ZH.md)：隔离测试与实车验收的范围。
- [手动驾驶说明](MANUAL_DRIVE.md)：统一控制台的键盘使用。

带日期的修复记录，以及 `archive/`、`TEACHER_PHYSICAL_NAVIGATION.md` 中的早期说明，保留用于追溯。它们记录的是当时状态，历史参数不覆盖当前运行配置和操作手册。

本地源码目录中的 `physical_runtime.yaml` 是模板；机器人的同名文件保存当前地图、桌面标定和现场设置。部署整理时不能用空模板覆盖现场配置。
