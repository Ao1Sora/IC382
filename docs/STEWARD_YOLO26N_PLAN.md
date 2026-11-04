# IC382 Steward Robot 感知分类实施计划书（YOLO26n）

版本：1.0  
日期：2026-11-04  
对应规范：`steward_robot_master_task_technical_specification.md`  
范围：CV-01～CV-05、INT-01（ME-01 实体贴标机构与 Porter 硬件不在软件交付内）

---

## 1. 结论摘要

1. 感知栈采用 **单一 TensorRT 推理实例 + 三个 ROS2 节点**：
   `safety_monitor`（唯一 YOLO26n 实例，负责行人安全与原始检测）、
   `object_classifier`（五类映射、异常过滤、2D→3D）、
   `fair_chance_manager`（两轮巡检、资格判定、贴标/Porter、决策日志）。
2. 模型使用 **YOLO26n**。规范原建议 yolo26s；nano 更轻、更适合 Orin Nano，
   但 COCO mAP50-95 约 40.9（s 为 48.6）。本计划设置精度门槛，不达标时只切换权重到
   yolo26s，节点代码不变。
3. 当前可先用仓库外的 **COCO 预训练 `yolo26n.pt`** 做 bring-up：只启用 `person`
   安全检测，A/B/C 贴标一律禁用，未声明类记为 `out_of_scope`，绝不误标。
4. 数据现状只有 Isaac Sim 合成管线；**五类 `best.pt` 与 TensorRT engine 需数据到位后训练**。
   本计划同时交付训练、导出、基准与数据校验脚本。
5. 贴标/Porter 只能由 `fair_chance_manager` 在**第二轮复查确认后**发布；分类器在第一轮
   不得发布任何贴标坐标。

---

## 2. 现状与差距

| 项目 | 现状 | 差距 / 处理 |
|---|---|---|
| 接口 | `object_classifier` 仍导入上游已删除的 `PorterRequest/TaggingCommand`，节点启动失败 | 恢复并扩展消息；新增检测/分类/异常/安全/上下文消息 |
| 类别 | 代码 3 类（0/1/2→A/B/C），规范 5 类 | 内部五类；按**类名**映射，不假设 ID 顺序 |
| 模型 | 仅 COCO `yolov8n.pt` / `yolo26n.pt`，无团队权重 | `coco_bootstrap` 先用；`steward_v1` 待训练 |
| 推理 | `model(image)` 无 `conf/imgsz/device/half`，不支持 engine | 新 detector 参数与 TensorRT 路径 |
| 安全 | 无行人急停 | `safety_monitor` + `velocity_gate` 联锁 |
| 任务集成 | 自由运行图像回调，不接 `InspectDesk/CompleteInspection` | 事件驱动 + 两轮 manager |
| 资格 | 未实现 | person 距离 / reserved_card → INELIGIBLE |
| 3D | 单像素深度、最新时间 TF、失败静默回退相机系 | 深度中位数、图像时间戳 TF、失败不发布坐标 |
| 日志 | `results/decision_log.jsonl`，TAG 不写日志 | 规范 `/home/student/dev/decision_log.json` |
| 相机 | 默认 `/camera/image_raw` | 改为 Astra Pro `/camera/color/image_raw`，帧名参数化 |

---

## 3. 系统架构

### 3.1 节点与数据流

```
/camera/color/image_raw ─┐
/camera/depth/image_raw ─┼─► safety_monitor ──► /ic382/perception/detections
/camera/color/camera_info┘        │
                                  ├─► /ic382/safety_state
                                  ├─► /ic382/safety_stop ──► velocity_gate（AND）
                                  └─► /ic382/perception/status

/ic382/perception/detections ──► object_classifier ◄── /ic382/perception/context
                                        │
                                        ├─► /ic382/perception/classified
                                        ├─► /ic382/perception/anomalies
                                        └─► /ic382/perception/status

fair_chance_manager ◄── /ic382/perception/classified / anomalies / safety_state
        │
        ├─ ActionClient   /ic382/inspect_desk
        ├─ ServiceClient  /ic382/complete_inspection
        ├─ Publish        /ic382/perception/context
        ├─ Publish        /target_tag_pose, /tagging_cmd（确认后）
        ├─ Publish        /porter_cmd（任务结束）
        └─ Write          /home/student/dev/decision_log.json
```

### 3.2 职责边界

| 组件 | 负责 | 不得做 |
|---|---|---|
| `desk_navigation`（现有） | Nav2 路径、三点巡检、速度门授权、`InspectDesk`/`CompleteInspection` 服务端 | 识别、分类、贴标决策 |
| `safety_monitor`（新） | 唯一 YOLO 推理、行人距离、0.8/1.2 m 迟滞、`safety_stop` | 发布 `/cmd_vel`、`/ic382/allow_motion` |
| `object_classifier`（重构） | 五类映射、ROI、异常过滤、2D→3D、分类结果 | 第一轮发 TAG、两轮状态 |
| `fair_chance_manager`（新） | 两轮巡检编排、资格判定、贴标/Porter、决策日志 | 规划路径、发布速度 |
| `velocity_gate`（扩展） | 最终 `/cmd_vel`、看门狗、安全停车 | 识别 |
| `mission_journal`（现有） | `/ic382/events` 持久化与 ack | 感知决策 |

---

## 4. 模型选型与部署

### 4.1 YOLO26n

- 参数量约 2.4 M，COCO mAP50-95 约 40.9（e2e 40.1），CPU ONNX 约 39 ms。
- 无 DFL、可选 NMS-free 端到端；TensorRT FP16 在 Orin Nano 上预期 60–90 FPS
  （安全环 15–30 FPS 足够）。
- 与 yolo26s 对比：s 约 48.6 mAP、9.5 M 参数。nano 对小目标（reserved_card、远处 person）
  更敏感；若验证集门槛不达标，按第 6.4 节回退。

### 4.2 两种 profile

| Profile | 用途 | 允许贴标 | 类名要求 |
|---|---|---|---|
| `coco_bootstrap` | 先用 COCO 权重做安全与管线联调 | 否 | 仅需 `person` |
| `steward_v1` | 团队五类模型 | 是 | 五类必须全部存在，否则降级 observe-only |

映射按 `model.names` 的类名做，支持 `Class_A_IC_Material`、`class_a_ic_material` 等别名。
**绝不按数字 ID 猜类别**。

### 4.3 TensorRT

- RTX 3080：只导出 ONNX（`imgsz=640, opset=17, simplify`）。
- Jetson Orin Nano：在目标机用 `trtexec --fp16` 或 Ultralytics `format=engine half=True`
  构建 engine。engine 具有平台/版本绑定性。
- 不使用 INT8：TensorRT 10.x 的校准/精度在本项目不可靠；FP16 已验证足够。
- 启动时若 engine 反序列化失败，节点保持存活并发布 `detector_unavailable`，
  安全环按 `fail_safe_on_stale` 决定是否停车。

---

## 5. 数据管线（CV-01）

### 5.1 合成数据（Isaac Sim）

- 复用课程场景 `IC382_scene_Sep_v3` 与 `03_generate_dataset.py`；不把教师 USD 资产复制进 git。
- `tools/sim_dataset/generate_synthetic.py` 负责调用课程脚本并记录场景/脚本 SHA256。
- 目标：≥1000 张、每类 ≥300 实例、3 个桌面视角 ±10 cm/±5°、yaw 0–360°、
  遮挡 0–40%、多光源/背景、约 10% 空桌负样本。
- 按场景/光照/布局划分 train/val/test，禁止逐帧随机划分造成泄漏。

### 5.2 实拍数据

- 每类 10–20 张，两种光照、三个视角、两个距离、部分遮挡、空桌/异常物负样本。
- 使用机器人同款 Astra Pro 与近似安装高度；记录相机高度、俯仰与内参。
- 保留原图；Roboflow 只做标注/审核；增强只作用于训练集。
- 详细规范：`tools/labeling/capture_protocol.md`。

### 5.3 Roboflow 五类

```
0 ic_material   1 personal   2 disposables   3 person   4 reserved_card
```

导出 YOLO 格式，使用 `tools/dataset/validate_dataset.py` 检查类名、标签范围、
图像/标签配对与跨 split 重复哈希。

### 5.4 混合与划分

- `tools/dataset/build_dataset.py`：合成按场景分组划分；实拍按拍摄 session 分组划分；
  训练集对实拍做 `--real-repeat 5`（可按 3–10 调整）。
- 验证集 = 合成 val + 实拍 val；**主门槛 = 实拍 test**，合成 test 仅参考。
- 加入 5–10% 空桌/负样本降低误检。

---

## 6. 训练与导出（CV-02）

### 6.1 环境

- RTX 3080 16 GB，CUDA torch，`ultralytics>=8.3.222`（`yolo26n.pt` 内嵌 8.3.222；
  仓库原 `8.3.0` 太旧，已更新 requirements）。
- CI 不安装 ultralytics/torch；代码保持 lazy import。

### 6.2 超参数（`scripts/train-yolo26n.py`）

| 参数 | 值 |
|---|---|
| epochs | 100 |
| imgsz | 640 |
| batch | 16（OOM 先降到 8，不先降 imgsz） |
| amp | 开 |
| optimizer | auto |
| patience / close_mosaic | 20 / 10 |
| augmentation | mosaic 1.0, mixup 0.1, HSV, degrees 10, translate 0.1, scale 0.5, shear 2, perspective 0.0005, fliplr 0.5 |
| 预训练 | `yolo26n.pt` |

### 6.3 指标门槛（实拍 test 为主）

| 指标 | 门槛 |
|---|---|
| 总体 mAP50 / mAP50-95 | ≥0.85 / ≥0.55 |
| person mAP50 / recall@0.35 | ≥0.85 / ≥0.90 |
| reserved_card mAP50 | ≥0.80 |
| A/B/C 互混 | 每类 ≤10% |
| 空桌误检 | ≤1/10 帧 |
| out-of-scope 贴标 | **0（硬门槛）** |

### 6.4 回退规则

若 yolo26n 未过门槛，先补该类数据/提高输入尺寸评估；仍不达标时切换到 yolo26s，
要求整体 mAP50 至少提升 2 点且 Orin FP16 安全环仍 ≥15 FPS。切换只改权重与 profile。

### 6.5 导出

```bash
# RTX 3080 -> ONNX
python scripts/export-yolo26n.py --weights best.pt --format onnx --imgsz 640 --opset 17 --simplify

# Jetson Orin Nano -> TensorRT FP16（必须在 Jetson 上执行）
python scripts/export-yolo26n.py --weights best.onnx --format engine --half --imgsz 640

# 验证与基准
python scripts/check-model.py --weights /home/student/dev/models/steward_v1.engine
python scripts/benchmark-yolo26n.py --model /home/student/dev/models/steward_v1.engine --half
```

---

## 7. ROS2 实现

### 7.1 CV-03 行人安全（`safety_monitor.py`）

- 15–30 FPS 连续推理；`message_filters.ApproximateTimeSynchronizer` 同步彩色/深度/内参。
- 距离：bbox 下中部深度中位数；无深度时 `fy * 1.7 m / bbox_height_px`；两者皆无时按
  `unknown_distance_stop` 处理。
- 迟滞：≤0.8 m 连续 `confirm_frames` 停车；>1.2 m 连续 `clear_frames` 恢复；
  中间保持；传感器超时 → `SENSOR_STALE`（物理模式停车）。
- 发布 `/ic382/safety_stop`；`velocity_gate` 与 `/ic382/allow_motion` 做逻辑与。
- 物理 launch `require_safety: true`；仿真/无相机 `false`。

### 7.2 CV-04 分类与 INT-01 3D（`object_classifier.py`）

- 不持有 YOLO；订阅 `DetectedObjectArray` 与 `InspectionContext`。
- 只在 context active 时处理；按类名映射 role；ROI 过滤。
- 决策：
  - conf < 0.5 → `ANOMALY low_confidence`
  - 未声明类 → `ANOMALY out_of_scope`
  - person/reserved_card → `LOG_ONLY`（资格/安全）
  - bootstrap/tagging disabled → `LOG_ONLY`
  - 可贴标类 + 置信度达标 + 有效 3D → `TAG 候选`
- 2D→3D：`sample_depth_patch` 中位数；`pixel_to_3d`；用检测时间戳查
  `base_link ← camera_frame`；TF/深度失败 → `position_valid=false`，不发布坐标。
- 发布 `ObjectDetectionArray`（带 task/desk/point/round）与 `AnomalyReport`。
- 默认 `/camera/color/image_raw`；深度未对齐时禁用贴标。

### 7.3 CV-05 两轮公平机会（`fair_chance_manager.py`）

- 通过 action feedback 的 `WAITING_FOR_WORK` 获知 task_id/point_id，发布
  `InspectionContext(active=true)`，观察 8 s，随后 `active=false` 并调用
  `CompleteInspection`。
- Round 1 遍历目标桌并合并候选；等待 `round2_delay_seconds`（默认 60 s，物理可 120 s）。
- Round 2 再遍历 ELIGIBLE 且有候选的桌：
  - 有 map 坐标时按 3D 距离 ≤0.25 m 关联；无 3D 时回退 IoU（≥0.3）/中心距离比（≤0.6）。
  - `CONFIRMED_ABANDONED`：仍在原处；`OWNER_RETURNED`：已消失；
    `DESK_NOW_OCCUPIED`：桌面被人/保留牌占用；`NEW_ITEM_ANOMALOUS`：仅第二轮出现的新物。
- 仅 `CONFIRMED_ABANDONED`、role ∈ A/B/C、桌面 ELIGIBLE、无安全停车时发布
  `/target_tag_pose` 与 `/tagging_cmd`。
- 任务结束发布一次 `/porter_cmd`（确认废弃的 Class C 桌号/物品）。
- 不发布 `/cmd_vel`、`/ic382/allow_motion`、`/ic382/mission_status`。

### 7.4 决策日志

- `fair_chance_manager` 写 `/home/student/dev/decision_log.json`（原子替换）。
- 结构严格按规范：

```json
{
  "mission_timestamp": "2026-11-04T14:30:00Z",
  "desk_records": [
    {
      "desk_id": "T02",
      "desk_status": "ELIGIBLE",
      "round_1_seen": [
        {"item_id": 1, "class": "Class_C_Disposables", "confidence": 0.92, "timestamp": "14:31:05"}
      ],
      "round_2_validation": [
        {"item_id": 1, "status": "CONFIRMED_ABANDONED", "action_taken": "TAGGED_CLASS_C"}
      ],
      "anomalous_items": []
    }
  ]
}
```

- `action_taken`：`TAGGED_CLASS_A/B/C`、`NO_TAG_OWNER_RETURNED`、
  `NO_TAG_DESK_OCCUPIED`、`NO_TAG_ANOMALOUS`、`NO_TAG_INELIGIBLE`、`NO_TAG_UNKNOWN`。
- 另有可选 JSONL 审计路径；规范 JSON 为准。

---

## 8. 接口与话题

| 接口 | 类型 | 发布者 | 订阅者 |
|---|---|---|---|
| `/ic382/inspect_desk` | `InspectDesk` action | desk_navigation | fair_chance_manager |
| `/ic382/complete_inspection` | `CompleteInspection` service | desk_navigation | fair_chance_manager |
| `/ic382/perception/detections` | `DetectedObjectArray` | safety_monitor | object_classifier |
| `/ic382/perception/classified` | `ObjectDetectionArray` | object_classifier | fair_chance_manager |
| `/ic382/perception/anomalies` | `AnomalyReport` | object_classifier | fair_chance_manager |
| `/ic382/perception/context` | `InspectionContext` | fair_chance_manager | object_classifier |
| `/ic382/perception/status` | `std_msgs/String` JSON | safety_monitor / object_classifier | manager, diagnostics |
| `/ic382/safety_state` | `SafetyState` | safety_monitor | manager, diagnostics |
| `/ic382/safety_stop` | `std_msgs/Bool` | safety_monitor | velocity_gate |
| `/target_tag_pose` | `PoseStamped`（base_link） | fair_chance_manager | ME-01 |
| `/tagging_cmd` | `TaggingCommand` | fair_chance_manager | ME-01 |
| `/porter_cmd` | `PorterRequest` | fair_chance_manager | Porter |

消息定义见 `ros2_ws/src/ic382_interfaces/msg/`。

---

## 9. 部署与启动

### 9.1 权重放置

`*.pt/*.onnx/*.engine` 已被 `.gitignore` 忽略，不进入 git。

- Jetson：`/home/student/dev/models/yolo26n.pt`（bootstrap）或
  `/home/student/dev/models/steward_v1_fp16.engine`（正式）。
- 启动时用 `model_path:=...` 覆盖；不要写死机器路径到仓库配置。

### 9.2 启动

```bash
# 仅感知（独立调试）
ros2 launch ic382_perception perception.launch.py \
  model_path:=/home/student/dev/models/yolo26n.pt \
  model_profile:=coco_bootstrap tagging_enabled:=false

# 物理导航 + 感知
ros2 launch ic382_navigation navigation.launch.py config_file:=.../physical_runtime.yaml

# 团队 manifest（仿真/联调）
ros2 launch ic382_bringup team.launch.py
```

`physical_runtime.yaml` 已加入 `start_perception/model_profile/model_path/tagging_enabled/
perception_required/require_safety`。正式五类模型通过门槛后改为：

```yaml
model_profile: steward_v1
tagging_enabled: true
perception_required: true
```

### 9.3 Isaac Sim 相机桥

当前 `IC382-hpc-isaac-sim-env` 场景只有 `base_link -> camera_link` 挂点，没有 ROS2
图像发布。运行仿真时在 HPC 主机执行：

```bash
bash robot-ros2/scripts/isaac-camera-bridge.sh
```

仿真循环会执行一次 `logs/course601-runtime-request.py`，在 `base_link/camera_link`
下创建相机并发布到 ROS domain 82：

- `/camera/color/image_raw`（rgb8）
- `/camera/depth/image_raw`（32FC1，米，已对齐）
- `/camera/color/camera_info`（fx/fy 非零）
- TF `base_link -> camera_link`（仿真已发布）

仿真配置使用 `camera_frame: camera_link`；物理 Astra 配置仍用
`camera_color_optical_frame`。

### 9.4 预检

```bash
python scripts/check-perception-inputs.py --camera-frame camera_link
```

检查话题频率、CameraInfo 内参、彩色/深度尺寸、`base_link ← camera_link` TF；
不移动机器人。仿真 ROS 容器需安装 `ultralytics>=8.3.222`，并把 `.pt` 权重放到
`model_path`（例如 `/workspace/robot-ros2/models/yolo26n.pt`）。

---

## 10. 测试与验收

### 10.1 本地 / CI

- 纯模块测试（不依赖 ROS/ultralytics）：类别映射、profile、决策、投影、安全迟滞、
  两轮关联、资格、决策日志、VelocityGate 安全位。
- `colcon build` + `colcon test` 在 ROS 2 Humble CI 全绿。
- 预训练权重检查：

```bash
python scripts/check-model.py --weights /path/yolo26n.pt --profile coco_bootstrap
```

### 10.2 Jetson 现场

- Astra Pro 话题与内参确认；`/ic382/perception/detections` 达 15–30 FPS。
- TensorRT FP16 安全环 ≥15 FPS（目标 20–25），分类 ≥5 FPS。
- 真人 0.8 m 停车、1.2 m 恢复；断开安全节点/相机时 `velocity_gate` 停车。
- 两轮巡检后 `decision_log.json` 结构与值正确；Porter 只在任务结束收到一次列表。

### 10.3 HPC 仿真

无相机桥，使用 `require_safety:false` + mock 检测，跑通
`InspectDesk → WAITING_FOR_WORK → context → classified → CompleteInspection` 握手。

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 五类数据未就绪 | 无法训练正式模型 | 先交付脚本与 bootstrap；数据到位后按门槛训练 |
| yolo26n 小目标精度不足 | reserved_card / 远处 person 漏检 | 补数据、提高输入尺寸评估、按规则回退 yolo26s |
| 合成→真实域差异 | 实拍误检/漏检 | 实拍重复采样、按场景划分、实拍 test 为主门槛 |
| TensorRT 版本/平台 | engine 无法加载 | 只在目标 Jetson 构建；记录版本/SHA256；失败时安全降级 |
| 相机深度未对齐 | 3D 坐标错误 | `depth_is_aligned` 参数；未确认时禁用贴标 |
| 资格/两轮为启发式 | 误判占用/归属 | 阈值参数化；现场调参；异常一律不贴标 |
| 接口恢复与上游冲突 | 合并冲突 | 消息集中在 `ic382_interfaces`；与团队确认命名 |
| 贴标时机 | 第二轮末机器人不在检测点 | 当前接口携带 base_link 坐标与时间戳；ME-01 集成时用 TF 变换到当前时刻 |

---

## 12. 交付物矩阵

| 编号 | 交付物 | 位置 |
|---|---|---|
| CV-01 | 数据规范、合成适配器、数据集校验/混合脚本 | `tools/sim_dataset/`, `tools/labeling/`, `tools/dataset/` |
| CV-02 | 训练/导出/基准脚本、指标门槛 | `scripts/train-yolo26n.py`, `export-yolo26n.py`, `benchmark-yolo26n.py`, `tools/training/` |
| CV-03 | 安全监控节点 | `ic382_perception/safety_monitor.py`, `safety.py` |
| CV-04 | 分类/异常/3D 节点 | `ic382_perception/object_classifier.py`, `model_profile.py`, `decision.py`, `transform.py` |
| CV-05 | 两轮公平机会与日志 | `ic382_perception/fair_chance_manager.py`, `fair_chance.py`, `eligibility.py`, `decision_log.py` |
| INT-01 | `/target_tag_pose` 与消息 | `fair_chance_manager.py`, `ic382_interfaces/msg/` |

---

## 13. 建议时程

| 周 | 工作 |
|---|---|
| W1 | 接口/模型层/安全节点；bootstrap 权重联调 |
| W2 | 分类节点、3D 投影、决策日志；mock 端到端 |
| W3 | 两轮 manager、launch 集成、CI 测试 |
| W4 | 合成数据生成 + 实拍标注；数据集校验 |
| W5–W6 | YOLO26n 训练、指标门槛、ONNX 导出 |
| W7 | Jetson TensorRT FP16、现场安全/两轮调参、验收 |

数据未就绪不阻塞 W1–W3；训练与现场验收按数据到位时间顺延。

---

## 附录 A：决策日志示例

```json
{
  "mission_timestamp": "2026-11-04T14:30:00Z",
  "desk_records": [
    {
      "desk_id": "T02",
      "desk_status": "ELIGIBLE",
      "round_1_seen": [
        {"item_id": 1, "class": "Class_C_Disposables", "confidence": 0.92, "timestamp": "14:31:05"}
      ],
      "round_2_validation": [
        {"item_id": 1, "status": "CONFIRMED_ABANDONED", "action_taken": "TAGGED_CLASS_C"}
      ],
      "anomalous_items": [
        {"class": "bottle", "confidence": 0.41, "reason": "low_confidence", "timestamp": "14:31:06"}
      ]
    }
  ]
}
```

## 附录 B：常用命令

```bash
# 模型 profile 校验
python scripts/check-model.py --weights /path/yolo26n.pt --profile coco_bootstrap

# 训练（RTX 3080）
python scripts/train-yolo26n.py --data datasets/combined_v1/dataset.yaml --weights yolo26n.pt

# 数据集校验
python tools/dataset/validate_dataset.py --data datasets/combined_v1/dataset.yaml

# Jetson 预检
python scripts/check-perception-inputs.py
```
