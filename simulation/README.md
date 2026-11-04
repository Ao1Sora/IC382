# HPC Isaac Sim adapter

The navigation action, three-of-four candidate selection, motion gate, journal
and work acknowledgement protocol are shared with the Jetson code. Physical
drivers are excluded from `simulation.launch.py`.

`config/runtime.yaml` is the runtime configuration. The existing course scene
uses ten scene units per physical metre. Table geometry and footprint are in
scene coordinates; `parking_distance_m` and `max_linear_mps` remain in physical
metres. Candidates are generated using the shared geometry routine before
conversion into scene units. Camera coverage is not calibrated.

The teacher course Nav2 YAML is copied from the previously downloaded original
course archive. It uses DWB, unlike the Jetson's installed MPPI profile. The
existing HPC DWB and encoder calibration overrides are retained in a separate
file. `simulation_encoder.py`, `simulation_integrator.py` and
`simulation_scan.py` are project adapters retained from the prior HPC checkout,
not teacher-authored code. AMCL now corrects encoder drift using the saved lidar
map. Simulator ground truth is not used as a live navigation input.

Both costmaps use the annotated static navigation map with inflation disabled.
The controller retains full footprint collision checking. Laser data is used
for localization and sensor freshness checks. The simulator's original scene,
installation and diagnostics remain outside this checkout.

## Perception in the Isaac Sim scene

The scene snapshot has only a static `base_link -> camera_link` mount; it does
not publish images yet. While the simulation is running, queue the included
bridge from the HPC host:

```bash
bash robot-ros2/scripts/isaac-camera-bridge.sh
```

The simulation loop executes `logs/course601-runtime-request.py` once, adds a
camera under `base_link/camera_link`, and publishes into ROS domain 82:

- `/camera/color/image_raw` (`sensor_msgs/Image`, rgb8)
- `/camera/depth/image_raw` (`sensor_msgs/Image`, aligned 32FC1 metres)
- `/camera/color/camera_info` (`sensor_msgs/CameraInfo`, non-zero fx/fy)
- frames: `base_link <- camera_link` (already in `/tf_static`)

If the bridge is not used, enable perception only after the scene publishes the
same topics and TF itself. The perception config uses `camera_frame: camera_link`;
the physical Astra config keeps `camera_color_optical_frame`.

Then set in `simulation/config/runtime.yaml`:

```yaml
start_perception: true
model_path: /workspace/robot-ros2/models/yolo26n.pt   # .pt/.onnx; not a Jetson engine
model_profile: coco_bootstrap
```

and adjust `simulation/config/perception_sim.yaml` if the scene uses different
topic names, depth encoding (`depth_scale: 1.0` for 32FC1 metres) or frames.
Run inside the ROS environment (domain 82):

```bash
python scripts/check-perception-inputs.py --camera-frame camera_link
```

before enabling it. The ROS container also needs `ultralytics` and the `.pt`
weight accessible at `model_path`.

The TensorRT `.engine` built for the Jetson is not portable to the Isaac Sim GPU;
use the `.pt` or ONNX weights in simulation. `tagging_enabled` stays false until
a five-class `steward_v1` checkpoint exists.

HPC entry: `scripts/start-robot-navigation.sh` in the environment loads
`robot-ros2/scripts/run-course-navigation.sh`. In the running simulation:

```bash
./robot-ros2/scripts/hpc-ros.sh bash -c 'source /workspace/robot-ros2/ros2_ws/install/setup.bash; python3 /workspace/robot-ros2/scripts/demo-inspect-desk.py --desk T04 --work-seconds 2 --output /workspace/robot-ros2/results/three-point-result.json'
```

The demo acknowledges placeholder inspection work. It does not perform actual
recognition or tagging. Goal success requires three Nav2 arrivals and three work
acknowledgements; software/interface test success alone is not a simulation pass.
