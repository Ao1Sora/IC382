# Course environment: original RTX lidar restored

Verified on 2026-10-14. The default course entry runs Isaac Sim 6.0.1, ROS2 Humble, and the course's original GPU OmniLidar. The PhysX CPU ray substitute is no longer used by the default simulation.

## Course source and sensor identity

Week 06 was read live after signing into Canvas:
https://canvas.polyu.edu.hk/courses/3487/files/286771?module_item_id=118044

Page 22 specifies Isaac Sim 6.0.1; page 27 specifies ROS2 Humble. Pages 24-25 use the supplied final_wheeltec_with_scene.usd; page 30 displays LaserScan.

The sensor was extracted from the fully loaded ORIGINAL supplied USD, not from the old HPC SLAMTEC replacement. It is OmniLidar with modelName Example_Rotary: 128 emitters/channels, 10 Hz nominal rotary scan rate, nearRangeM 1, farRangeM 600, original emitter timing, azimuth/error parameters, orientation and scale. Its authored configuration is preserved in dev/Collected_final_wheeltec_with_scene/course-original-lidar.usda. ROS2RtxLidarHelper now publishes its original GPU scan on /scan: 3600 rays, laser_link frame.

## Driver compatibility solution

HPC uses RTX 3080 Ti and NVIDIA driver 550.54.14. Standard PTX 8.7 JIT fails with CUDA_ERROR_UNSUPPORTED_PTX_VERSION. The complete CUDA forward-compatibility library failed with CUDA_ERROR_COMPAT_NOT_SUPPORTED_ON_DEVICE (804); swapping only its PTX compiler also failed.

A project-local CUDA loader forwards ordinary CUDA calls to the unchanged host driver. For the original sensor's CUDA link operations, NVIDIA's official CUDA 12.8 ptxas compiles the UNMODIFIED PTX modules as relocatable objects for sm_86; NVIDIA nvlink links all four modules into a GPU binary. The host driver then loads that binary. Material callbacks, sensor processing and original GPU ray tracing remain in the Isaac Sim 6.0.1 implementation. This does not substitute CPU raycasts or install a different sensor SDK.

The compatibility binary is approximately 1.59 MB. The proxy and compiler are selected only inside the course's Ubuntu wrapper; system libraries and the host kernel driver are unchanged. Driver verification override remains enabled. This tested project-specific adaptation is not a general vendor-supported configuration for every CUDA/Isaac Sim feature. The proxy is currently built for this host driver ABI and GPU architecture.

## Validation

- Original sensor in a simple scene: 30 consecutive ROS2 scans, 3600 rays each, 1124 positive returns. Four cubes with their nearest faces at 4 m produced a measured minimum of 3.9987 m. range_max remained 600 m. COURSE_ORIGINAL_LIDAR_PROBE_PASSED.
- Complete course robot/building scene: original GPU sensor and streaming server started; /clock, /odom and /scan advanced continuously. A stationary sample had 3560 valid distance returns, approximately 11.39–186.77 m. The other 40 rays used the original helper's -1 invalid sentinel; they are not counted as valid returns.
- External ROS2 control while the original lidar ran: forward/backward and left/right commands were received, independently sampled maximum displacement was 0.491 m, and final v/w commands were zero. Clock/odom counters reached 2261 and scan counter reached 375 during this sample. Timed demo labels are nominal and actual motion is printed separately.
- Shader/material modules compiled and linked successfully; no unsupported-PTX/invalid-resource errors were observed in this successful integrated run.
- Client 2.0.0 is launched in the VNC desktop. Streaming server readiness is verified; client-side connected interaction has not been independently checked.
- Original collected materials still contain some missing texture references. Cleaned geometry and reconstructed robot control graph are still used to avoid the original saved-graph crash. Autonomous Nav2 goal performance is not yet validated in this migration, so this is not a claim that every course exercise has been reproduced.

## Start and rebuild

Inside the allocated HPC VNC desktop:

```bash
cd ~/Desktop/IC382
./start-course.sh
./demo.sh
```

Connect the streaming client to 10.238.38.1. The existing course desktop shortcut uses the same entry. Closing the client cleans up its session.

The compiler is installed under tools/cuda-nvcc-12-8 using NVIDIA's official cuda-nvcc-12-8_12.8.93-1_amd64.deb. The CUDA proxy can be rebuilt with ./scripts/build-rtx-cuda-proxy.sh. Its implementation and forwarding assembly are scripts/rtx-cuda-proxy.c and scripts/rtx-cuda-forward.S. scripts/isaac601-ubuntu-rtx.sh maps this proxy inside the project environment. scripts/isaac601-python-rtx.sh launches the course interpreter using that wrapper.

Evidence: logs/course601-original-lidar-offline.log, logs/course601-original-lidar-probe.json, logs/course601-original-lidar-desktop.log, logs/course601-stream-simulation.log, logs/course601-live.json, logs/course601-demo-result.json, logs/course601-scene.png.

Official tool source: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/
CUDA forward compatibility limits: https://docs.nvidia.com/deploy/cuda-compatibility/forward-compatibility.html
