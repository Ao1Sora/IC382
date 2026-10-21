#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$project"
if [[ -z "${SLURM_JOB_ID:-}" ]];then
 job=$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -n1)
 [[ -n "$job" ]] || { echo 'No running GPU job.';exit 1; }
 exec srun --jobid="$job" --overlap --pty "$0" "$@"
fi
pid=$(pgrep -u "$(id -u)" -f '^bash .*/scripts/(course601-desktop|week06-stream-desktop)\.sh --isolated$' | head -n1 || true)
[[ -n "$pid" ]] || { echo 'Start IC382 course simulation first.';exit 1; }
exec nsenter -t "$pid" -U --preserve-credentials -n "$project/scripts/week06-ros.sh" python3 /workspace/scripts/course-demo.py "$@"
