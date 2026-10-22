#!/usr/bin/env bash
# R2 (generation-settings sensitivity) then R3 (false-negative audit), one GPU, in sequence.
# R2 reuses the ten models R1 kept; R3 pulls, runs and deletes one census artifact at a time.
set -euo pipefail
cd /root/p2/run
PY=/root/p2/venv/bin/python
bash start_ollama.sh

# R2 entries: the ten artifacts R1 kept
$PY - <<'EOF'
import json
E = [e for e in json.load(open("r1_entries.json")) if e.get("keep")]
json.dump(E, open("r2_entries.json", "w"), indent=1)
print(len(E), "R2 entries")
EOF

R2=/workspace/p2rerun/results-r2
declare -A SETTINGS=(
  [ctx4096]='{"num_ctx": 4096}'
  [ctx8192]='{"num_ctx": 8192}'
  [pred2048]='{"num_predict": 2048}'
  [t02s1]='{"temperature": 0.2, "seed": 1}'
  [t02s2]='{"temperature": 0.2, "seed": 2}'
  [t02s3]='{"temperature": 0.2, "seed": 3}'
)
for s in ctx4096 ctx8192 pred2048 t02s1 t02s2 t02s3; do
  $PY run_entries.py r2_entries.json --setting "$s" --options "${SETTINGS[$s]}" --results-dir "$R2" --no-hash
done
$PY score_runs.py "$R2"
echo R2_DONE

# R3 entries: the pre-drawn false-negative sample, 49 held-out tasks, nothing kept
$PY - <<'EOF'
import json
S = json.load(open("fn_sample_30.json"))["artifacts"]
E = [{"id": "fn-" + a["tag"].replace(":", "_").replace("/", "_"), "role": "fn-sample", "kind": "ollama",
      "tag": a["tag"], "family": a["family"]} for a in S]
json.dump(E, open("r3_entries.json", "w"), indent=1)
print(len(E), "R3 entries")
EOF
R3=/workspace/p2rerun/results-r3
$PY run_entries.py r3_entries.json --setting heldout49 --tasks heldout_49.json --results-dir "$R3" --no-hash
$PY score_runs.py "$R3"
df -h / | tail -1
echo R3_DONE
