#!/usr/bin/env bash
# Run a command in the EXISTING course simulation network and ROS container.
set -euo pipefail
environment=${IC382_ENV_ROOT:-"$HOME/Desktop/IC382"}
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  job=$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -n1)
  [[ -n "$job" ]] || { echo 'Allocate the HPC GPU job first.' >&2; exit 1; }
  exec srun --jobid="$job" --overlap -N1 -n1 "$0" "$@" </dev/null
fi
cd "$environment"
pid=$(pgrep -u "$(id -u)" -f '^bash .*/scripts/course601-desktop\.sh --isolated$' | head -n1 || true)
[[ -n "$pid" ]] || { echo 'Start the course simulation first.' >&2; exit 1; }
# The code checkout lives inside the existing /workspace bind mount. No new
# namespace, broad pkill, container bind or host-library changes are needed.
exec nsenter -t "$pid" -U --preserve-credentials -n "$environment/scripts/week06-ros.sh" "$@"
