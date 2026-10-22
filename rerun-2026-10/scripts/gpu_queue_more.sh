#!/usr/bin/env bash
# P0 GPU stages, run by gpu_queue.sh after R3b: smoke for the P0-f and P0-d builds, then P0-c (164 tasks).
set -uo pipefail
cd /root/p2/run
PY=/root/p2/venv/bin/python
L=/workspace/p2rerun/logs
# Retry pass: anything that errored earlier (e.g. a registry 503) reruns; finished entries are skipped
$PY run_entries.py r3_entries.json --setting heldout49 --tasks heldout_49.json --results-dir /workspace/p2rerun/results-r3 --no-hash
$PY run_entries.py r3b_entries.json --setting heldout49 --tasks heldout_49.json --results-dir /workspace/p2rerun/results-r3b --no-hash
$PY run_entries.py r5_entries.json --setting base --results-dir /workspace/p2rerun/results-r5
$PY run_entries.py r6_entries.json --setting full164 --tasks all164.json --results-dir /workspace/p2rerun/results-r6
echo RETRY_PASS_DONE
until grep -q P0_CPU_DONE $L/p0_cpu.log 2>/dev/null; do sleep 30; done

$PY - <<'EOF'
import json
Q = "qwen2.5-coder:3b-instruct-q4_K_M"; P = "phi3.5:3.8b-mini-instruct-q4_K_M"
W = "/workspace/p2rerun"
code_q = [{"id": f"codeimat-qwen3b-{q}", "role": "own-imatrix-code", "kind": "gguf", "path": f"{W}/quants-imat-code/qwen3b-codeimat-{q}.gguf", "donor": Q}
          for q in ("Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L")]
code_p = [{"id": f"codeimat-phi35-{q}", "role": "own-imatrix-code", "kind": "gguf", "path": f"{W}/quants-imat-code/phi35-codeimat-{q}.gguf", "donor": P}
          for q in ("Q2_K", "Q3_K_S", "Q3_K_M")]
libmix = {"id": "libmix-phi35-Q2_K", "role": "plain-libmix", "kind": "gguf", "path": f"{W}/quants/phi35-Q2_K-libmix.gguf", "donor": P}
json.dump([libmix] + code_q + code_p, open("p0_smoke_entries.json", "w"), indent=1)
full = [
 {"id": f"plain-phi35-{q}", "role": "plain", "kind": "gguf", "path": f"{W}/quants/phi35-{q}.gguf", "donor": P} for q in ("Q2_K", "Q3_K_S", "Q3_K_M")
] + [
 {"id": f"cal-phi35-{q}", "role": "own-imatrix", "kind": "gguf", "path": f"{W}/quants-imat/phi35-imat-{q}.gguf", "donor": P} for q in ("Q2_K", "Q3_K_S", "Q3_K_M")
] + [libmix,
 {"id": "lib-phi35-q4_K_M", "role": "sibling", "kind": "ollama", "tag": P, "keep": True},
 {"id": "imat-phi35-Q2_K", "role": "imatrix", "kind": "hf", "repo": "bartowski/Phi-3.5-mini-instruct-GGUF", "file": "Phi-3.5-mini-instruct-Q2_K.gguf", "donor": P},
] + [
 {"id": f"imat-qwen3b-{q}", "role": "imatrix", "kind": "hf", "repo": "bartowski/Qwen2.5-Coder-3B-Instruct-GGUF", "file": f"Qwen2.5-Coder-3B-Instruct-{q}.gguf", "donor": Q} for q in ("Q3_K_S", "Q3_K_M", "Q3_K_L")
] + code_q
json.dump(full, open("p0c_entries.json", "w"), indent=1)
print(len(full), "P0-c entries")
EOF

$PY run_entries.py p0_smoke_entries.json --setting base --results-dir /workspace/p2rerun/results-p0
echo P0_SMOKE_GEN_DONE
$PY run_entries.py p0c_entries.json --setting full164 --tasks all164.json --results-dir /workspace/p2rerun/results-p0c
echo P0C_GEN_DONE
