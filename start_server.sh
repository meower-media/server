#!/bin/bash

cmds=("python run_api.py" "python run_cl3.py" "python run_cl4.py")

for cmd in "${cmds[@]}"; do {
  echo "Process \"$cmd\" started";
  $cmd & pid=$!
  PID_LIST+=" $pid";
} done

trap "kill $PID_LIST" SIGINT

echo "Parallel processes have started";

wait $PID_LIST

echo
echo "All processes have completed";