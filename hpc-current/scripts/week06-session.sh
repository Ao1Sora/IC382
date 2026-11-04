#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project"
mode=${1:-navigation}
job=${SLURM_JOB_ID:-$(squeue -h -u "$(id -un)" -n ic382-ssh-dev -t RUNNING -o '%i' | head -1)}
[[ -n "$job" ]] || { echo 'First open Connect-Gui.cmd or Connect-Hpc.cmd to allocate a GPU job.'; exit 1; }
running() {
 [[ -f "logs/$1.pid" ]] || return 1
 local pid;pid=$(cat "logs/$1.pid")
 [[ "$pid" =~ ^[0-9]+$ ]] || return 1
 ps -p "$pid" -o args= | grep -q 'srun.*week06'
}
start() {
 local name=$1;shift
 if running "$name"; then echo "$name is already running";return;fi
 nohup srun --jobid="$job" --overlap -N1 -n1 "$@" > "logs/$name.log" 2>&1 < /dev/null &
 echo $! > "logs/$name.pid"
 echo "Started $name in GPU job $job"
}
stop_one() { if running "$1"; then kill -TERM "$(cat "logs/$1.pid")";fi; }
case "$mode" in
 stop)
  for name in week06-rviz week06-navigation week06-mapping week06-scan-adapter week06-transform week06-simulation;do stop_one "$name";done;;
 status)
  for name in week06-simulation week06-transform week06-scan-adapter week06-mapping week06-navigation week06-rviz;do if running "$name";then echo "$name RUNNING";else echo "$name STOPPED";fi;done;;
 keyboard) exec srun --jobid="$job" --overlap -N1 -n1 ./scripts/week06-keyboard.sh;;
 rviz) start week06-rviz ./scripts/week06-rviz.sh;;
 save-map) srun --jobid="$job" --overlap -N1 -n1 ./scripts/week06-save-map.sh < /dev/null;;
 mapping|navigation)
  launched=$(date +%s)
  if running week06-simulation;then launched=0;fi
  start week06-simulation ./scripts/week06-ubuntu.sh /workspace/scripts/week06-simulation.sh
  start week06-transform ./scripts/week06-transform.sh
  start week06-scan-adapter ./scripts/week06-ros.sh python3 /workspace/scripts/week06-scan-adapter.py
  for _ in $(seq 1 60);do if [[ -s logs/week06-live.json ]] && [[ $(stat -c %Y logs/week06-live.json) -ge "$launched" ]];then break;fi;sleep 2;done
  if [[ "$mode" == mapping ]];then
   stop_one week06-navigation
   start week06-mapping ./scripts/week06-mapping.sh
  else
   stop_one week06-mapping
   start week06-navigation ./scripts/week06-navigation.sh
   sleep 10
   srun --jobid="$job" --overlap -N1 -n1 ./scripts/week06-ros.sh python3 /workspace/scripts/week06-initial-pose.py < /dev/null
  fi
  start week06-rviz ./scripts/week06-rviz.sh;;
 *) echo 'Usage: week06-session.sh navigation|mapping|save-map|keyboard|rviz|status|stop';exit 2;;
esac
