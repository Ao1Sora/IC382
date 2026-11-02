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

HPC entry: `scripts/start-robot-navigation.sh` in the environment loads
`robot-ros2/scripts/run-course-navigation.sh`. In the running simulation:

```bash
./robot-ros2/scripts/hpc-ros.sh bash -c 'source /workspace/robot-ros2/ros2_ws/install/setup.bash; python3 /workspace/robot-ros2/scripts/demo-inspect-desk.py --desk T04 --work-seconds 2 --output /workspace/robot-ros2/results/three-point-result.json'
```

The demo acknowledges placeholder inspection work. It does not perform actual
recognition or tagging. Goal success requires three Nav2 arrivals and three work
acknowledgements; software/interface test success alone is not a simulation pass.
