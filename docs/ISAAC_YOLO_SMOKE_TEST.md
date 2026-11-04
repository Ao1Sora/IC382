# Isaac Sim 本地 YOLO26n 冒烟测试

目标：在 Ubuntu + Isaac Sim 6.0.1 上，用已搭好的 USD 场景采集相机帧，再用普通 Python
跑 `yolo26n.pt`，看模型在仿真画面上的检测效果。**不需要 ROS2、colcon 或感知节点。**

## 0. 场景与权重

```bash
ENV=~/IC382-hpc-isaac-sim-env
SCENE=$ENV/dev/Collected_final_wheeltec_with_scene/final_wheeltec_hpc45_clean.usdc
ls -l "$SCENE"     # 约 513 MB；134 字节表示 Git LFS 未拉取
# 如果是指针：cd "$ENV" && git lfs pull
```

把 `yolo26n.pt` 放在本机，例如 `~/yolo26n.pt`。

## 1. 采集 Isaac Sim 帧

```bash
# 先列出场景里的相机 prim（可能没有）
~/isaacsim/python.sh scripts/isaac-capture-frames.py \
  --scene "$SCENE" --list-cameras

# 有相机：用现有相机
~/isaacsim/python.sh scripts/isaac-capture-frames.py \
  --scene "$SCENE" --camera-prim /World/.../Camera \
  --frames 20 --output ~/ic382_frames

# 没有相机：用全景视角，之后按桌面坐标再调整
~/isaacsim/python.sh scripts/isaac-capture-frames.py \
  --scene "$SCENE" --position 10 10 15 --look-at 0 0 0 \
  --frames 20 --output ~/ic382_frames

# 场景材质/引用报错时，可先修复（不修改原 USD）
~/isaacsim/python.sh scripts/isaac-capture-frames.py \
  --scene "$SCENE" \
  --repair-script "$ENV/scripts/repair-course-scene.py" \
  --position 10 10 15 --look-at 0 0 0 \
  --frames 20 --output ~/ic382_frames
```

无显示器时加 `--headless`。输出目录应包含 `frame_0000.png ...` 和 `metadata.json`。

## 2. 普通 Python 推理

不要用 Isaac Sim 自带 Python；建独立 venv，避免依赖冲突：

```bash
python3 -m venv ~/ic382-yolo
source ~/ic382-yolo/bin/activate
pip install "ultralytics>=8.3.222"
# 如需 GPU：按 https://pytorch.org 先安装对应 CUDA 版本的 torch

python scripts/yolo-infer-images.py \
  --images ~/ic382_frames \
  --weights ~/yolo26n.pt \
  --output ~/ic382_annotated \
  --device 0
```

输出：
- `~/ic382_annotated/frame_0000_annotated.jpg`：带框图片。
- `~/ic382_annotated/detections.json`：每张图的类别、置信度、bbox、团队角色统计。

## 3. 结果解读

- 当前权重是 COCO-80；能识别 `person / laptop / bottle / cup / cell phone` 等。
- 这次**不会**出现 `ic_material / personal / disposables / reserved_card`；那些是自训练五类模型。
- `detections.json` 的 `role_counts` 里，COCO 的 `person` 会映射为 `PERSON`，其余多为
  `OUT_OF_SCOPE`，这是预期行为。

## 4. 常见问题

| 现象 | 处理 |
|---|---|
| USD 只有 134 字节 | `git lfs pull` 或从完整环境拷贝 USD/贴图 |
| `Stage did not load` | 检查 USD 路径、贴图目录；尝试 `--repair-script` |
| 采集全黑/无物体 | 调整 `--position/--look-at` 到桌面视角；先看全景 |
| `--headless` 渲染失败 | 去掉 `--headless` 用 GUI 运行 |
| `--device 0` 报错 | venv 里是 CPU torch；改 `--device cpu` 或装 CUDA torch |
| 没有检测框 | 画面里没有 COCO 类物体、灯光太暗或 `--conf` 太高；先调视角/降低 conf |
