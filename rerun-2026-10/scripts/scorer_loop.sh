#!/usr/bin/env bash
# Score every results directory continuously on the CPU (6 workers) while the GPU generates.
# Exits after the GPU queue is done and a final pass has scored everything.
cd /root/p2/run
PY=/root/p2/venv/bin/python
L=/workspace/p2rerun/logs
while true; do
  final=0
  grep -q GPU_QUEUE_DONE $L/gpu_queue.log 2>/dev/null && final=1
  for d in /workspace/p2rerun/results-*; do
    nice -n 5 $PY score_runs.py "$d" 6
  done
  if [ $final = 1 ]; then echo SCORER_DONE; break; fi
  sleep 60
done
