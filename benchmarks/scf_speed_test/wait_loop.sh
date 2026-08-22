#!/bin/bash
IDS=$(awk '{print $1}' /home/gilles/Al_C/benchmarks/scf_speed_test/submitted_ids.txt | paste -sd,)
echo "$(date '+%F %T') waiting on: $IDS"
while true; do
  N=$(squeue -j "$IDS" -h -o "%i" 2>/dev/null | wc -l)
  echo "$(date '+%F %T') jobs still in queue: $N"
  if [ "$N" -eq 0 ]; then
    break
  fi
  sleep 60
done
echo "$(date '+%F %T') all benchmark jobs finished"
