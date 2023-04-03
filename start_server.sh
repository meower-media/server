#!/bin/bash

cmds=("python run_api.py" "python run_cl3.py" "python background_worker.py")

for cmd in "${cmds[@]}"; do {
  echo "Process \"$cmd\" started";
  $cmd & pid=$!
  PID_LIST+=" $pid";
  sleep 2
} done

trap "kill $PID_LIST" SIGINT

echo "Parallel processes have started";

wait $PID_LIST

echo
echo "All processes have completed";