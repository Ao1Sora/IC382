#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo 'Run inside the GPU allocation using Connect-Hpc.cmd.' >&2
  exit 1
fi
threads=${SLURM_CPUS_PER_TASK:-6}
export OMP_NUM_THREADS="$threads" OPENBLAS_NUM_THREADS="$threads" MKL_NUM_THREADS="$threads"
exec "$project/tools/isaacsim-4.5.0/python.sh" "$@"
