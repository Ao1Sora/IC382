#!/usr/bin/env bash
set -euo pipefail
environment=${IC382_ENV_ROOT:-"$HOME/Desktop/IC382"}
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  job=$(squeue -h -u "$(id -un)" -t RUNNING -o '%i|%P' | awk -F'|' '$2=="h07gpuq1" {print $1;exit}')
  [[ -n "$job" ]] || { echo 'No running GPU job'; exit 1; }
  exec srun --jobid="$job" --overlap -N1 -n1 "$0" "$@" </dev/null
fi
pid=$(pgrep -u "$(id -u)" -f '^bash .*/scripts/course601-desktop\.sh --isolated$' | head -n1 || true)
[[ -n "$pid" ]] || { echo 'Isaac scene is not running'; exit 1; }
exec nsenter -t "$pid" -U --preserve-credentials -n "$environment/scripts/week06-ros.sh" "$@"
