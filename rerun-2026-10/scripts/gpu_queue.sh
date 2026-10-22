#!/usr/bin/env bash
# GPU generation queue, back to back. Scoring runs separately (scorer_loop.sh) so the GPU never
# waits on EvalPlus. Replaces the tail of r2_r3.sh and queue_tail.sh. Every stage is resumable.
set -uo pipefail
cd /root/p2/run
PY=/root/p2/venv/bin/python
L=/workspace/p2rerun/logs
bash start_ollama.sh

# R3: first false-negative sample, 49 held-out tasks, nothing kept
$PY - <<'EOF'
import json
S = json.load(open("fn_sample_30.json"))["artifacts"]
json.dump([{"id": "fn-" + a["tag"].replace(":", "_").replace("/", "_"), "role": "fn-sample", "kind": "ollama",
            "tag": a["tag"], "family": a["family"]} for a in S], open("r3_entries.json", "w"), indent=1)
S = json.load(open("fn_sample_b.json"))["artifacts"]
json.dump([{"id": "fn-" + a["tag"].replace(":", "_").replace("/", "_"), "role": "fn-sample-b", "kind": "ollama",
            "tag": a["tag"], "family": a["family"]} for a in S], open("r3b_entries.json", "w"), indent=1)
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
print("entries written")
EOF

$PY run_entries.py r3_entries.json --setting heldout49 --tasks heldout_49.json --results-dir /workspace/p2rerun/results-r3 --no-hash
echo R3_GEN_DONE
until grep -q IMATRIX_DONE $L/imatrix.log 2>/dev/null; do sleep 15; done
$PY run_entries.py r5_entries.json --setting base --results-dir /workspace/p2rerun/results-r5
echo R5_GEN_DONE
$PY run_entries.py r6_entries.json --setting full164 --tasks all164.json --results-dir /workspace/p2rerun/results-r6
echo R6_GEN_DONE
$PY run_entries.py r3b_entries.json --setting heldout49 --tasks heldout_49.json --results-dir /workspace/p2rerun/results-r3b --no-hash
echo R3B_GEN_DONE

# Further GPU stages are appended to gpu_queue_more.sh and run here if present
if [ -f gpu_queue_more.sh ]; then bash gpu_queue_more.sh; fi
df -h / | tail -1
echo GPU_QUEUE_DONE
