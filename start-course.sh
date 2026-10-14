#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$project"
if [[ -z "${SLURM_JOB_ID:-}" ]];then
 job=$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -1)
 [[ -n "$job" ]] || { echo 'Connect-Hpc.cmd: allocate your GPU job first.';exit 1; }
 exec srun --jobid="$job" --overlap -N1 -n1 "$0"
fi
exec ./scripts/week06-stream-desktop.sh
