#!/usr/bin/env bash
# R1: build plain referees, then score suspects, siblings and all referees in one session.
# Quantization runs before the library pulls so the 50 GB local disk is never over-committed.
set -euo pipefail
cd /root/p2/run
PY=/root/p2/venv/bin/python
RES=/workspace/p2rerun/results
bash start_ollama.sh
[ -f /root/quants/phi35-Q3_K_M.gguf ] || bash quantize_refs.sh > /workspace/p2rerun/logs/quantize.log 2>&1
$PY run_entries.py r1_entries.json --setting base --results-dir "$RES"
$PY score_runs.py "$RES"
df -h / | tail -1
echo R1_DONE
