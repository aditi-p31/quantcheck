#!/usr/bin/env bash
# GPU queue after R3: R5 (our own imatrix referees), R6 (full 164 tasks), R3b (second FN sample).
# Waits for R3 to finish and for the CPU imatrix job, so the GPU never runs two jobs at once.
set -euo pipefail
cd /root/p2/run
PY=/root/p2/venv/bin/python
L=/workspace/p2rerun/logs
QI=/workspace/p2rerun/quants-imat
QP=/workspace/p2rerun/quants
until grep -q R3_DONE $L/r2_r3.log 2>/dev/null; do sleep 15; done
until grep -q IMATRIX_DONE $L/imatrix.log 2>/dev/null; do sleep 15; done
bash start_ollama.sh

$PY - <<'EOF'
import json
Q = "qwen2.5-coder:3b-instruct-q4_K_M"; P = "phi3.5:3.8b-mini-instruct-q4_K_M"
QI = "/workspace/p2rerun/quants-imat"
r5 = [{"id": f"cal-qwen3b-{q}", "role": "own-imatrix", "kind": "gguf", "path": f"{QI}/qwen3b-imat-{q}.gguf", "donor": Q}
      for q in ("Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L")]
r5 += [{"id": f"cal-phi35-{q}", "role": "own-imatrix", "kind": "gguf", "path": f"{QI}/phi35-imat-{q}.gguf", "donor": P}
       for q in ("Q2_K", "Q3_K_S", "Q3_K_M")]
json.dump(r5, open("r5_entries.json", "w"), indent=1)
r6 = [e for e in r5 if e["id"].startswith("cal-qwen3b")]
r6 += [
 {"id": "imat-qwen3b-Q2_K", "role": "imatrix", "kind": "hf", "repo": "bartowski/Qwen2.5-Coder-3B-Instruct-GGUF", "file": "Qwen2.5-Coder-3B-Instruct-Q2_K.gguf", "donor": Q},
 {"id": "awq-qwen3b-q2_k", "role": "awq", "kind": "hf", "repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", "file": "qwen2.5-coder-3b-instruct-q2_k.gguf", "donor": Q},
 {"id": "awq-qwen3b-q3_k_m", "role": "awq", "kind": "hf", "repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", "file": "qwen2.5-coder-3b-instruct-q3_k_m.gguf", "donor": Q},
 {"id": "plain-qwen3b-Q4_K_M", "role": "plain-control", "kind": "gguf", "path": "/workspace/p2rerun/quants/qwen3b-Q4_K_M.gguf", "donor": Q},
 {"id": "lib-qwen3b-q4_K_M", "role": "sibling", "kind": "ollama", "tag": Q, "keep": True},
]
json.dump(r6, open("r6_entries.json", "w"), indent=1)
from evalplus.data import get_human_eval_plus
json.dump(sorted(get_human_eval_plus()), open("all164.json", "w"))
S = json.load(open("fn_sample_b.json"))["artifacts"]
json.dump([{"id": "fn-" + a["tag"].replace(":", "_").replace("/", "_"), "role": "fn-sample-b", "kind": "ollama",
            "tag": a["tag"], "family": a["family"]} for a in S], open("r3b_entries.json", "w"), indent=1)
print(len(r5), "R5,", len(r6), "R6,", len(S), "R3b entries")
EOF

$PY run_entries.py r5_entries.json --setting base --results-dir /workspace/p2rerun/results-r5
$PY score_runs.py /workspace/p2rerun/results-r5
echo R5_DONE
$PY run_entries.py r6_entries.json --setting full164 --tasks all164.json --results-dir /workspace/p2rerun/results-r6
$PY score_runs.py /workspace/p2rerun/results-r6
echo R6_DONE
$PY run_entries.py r3b_entries.json --setting heldout49 --tasks heldout_49.json --results-dir /workspace/p2rerun/results-r3b --no-hash
$PY score_runs.py /workspace/p2rerun/results-r3b
df -h / | tail -1
echo QUEUE_DONE
