#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
 echo 'Run inside an existing Slurm GPU allocation.' >&2
 exit 1
fi
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-6}" OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-6}" MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-6}"
exec "$project/scripts/isaac601-ubuntu-rtx.sh" -c '
 unset DISPLAY WAYLAND_DISPLAY PYTHONPATH
 export ROS_DISTRO=humble RMW_IMPLEMENTATION=rmw_fastrtps_cpp
 export LD_LIBRARY_PATH=/opt/nvidia/lib:/workspace/tools/isaacsim-6.0.1/exts/isaacsim.ros2.core/humble/lib
 exec /workspace/tools/isaacsim-6.0.1/python.sh "$@"
' -- "$@"
