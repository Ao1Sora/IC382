# Isaac Sim synthetic-data adapter

The course scene and `03_generate_dataset.py` live in the separate Isaac Sim
environment, not in this repository. Do not copy teacher USD assets into git.
This adapter records the scene/script provenance and invokes the course
generator with the team's settings.

## Run on the Isaac Sim host

```bash
~/Applications/IsaacSim/6.0.1/python.sh tools/sim_dataset/generate_synthetic.py \
  --course-script /path/to/03_generate_dataset.py \
  --scene /path/to/IC382_scene_Sep_v3.usd \
  --output datasets/sim/sep_v3 \
  --images 1000 \
  --seed 0
```

Targets: at least 1000 images, at least 300 instances per class, three desk
viewpoints with ±10 cm / ±5° jitter, yaw 0–360°, 0–40% occlusion, multiple
lighting conditions/backgrounds, and about 10% empty-desk negatives. Split by
scene/lighting/arrangement, not by random frame.

`scene_config.yaml` documents the settings expected by the generator. If the
course script does not read these environment variables, edit its STUDENT
SETTINGS block and record the change in `provenance.json`.
