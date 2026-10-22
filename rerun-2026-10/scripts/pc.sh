#!/usr/bin/env bash
# Positive control for our own conversion pipeline: the same Qwen checkpoint, the same llama.cpp,
# at high precision. If these fail too, the pipeline is broken and the plain low-bit result means
# nothing. Added 2026-10-21 after plain Qwen Q2_K..Q3_K_L all scored 0/15; it does not change the rule.
set -euo pipefail
cd /root/p2/run
B=/root/p2
PY=$B/venv/bin/python
REV=488639f1ff808d1d3d0ba301aef8c11461451ec5
mkdir -p /root/src /root/f16 /root/quants
if [ ! -f /root/f16/qwen3b-f16.gguf ]; then
  $PY -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-Coder-3B-Instruct', revision='$REV', local_dir='/root/src/qwen3b', allow_patterns=['*.json','*.safetensors','*.txt','tokenizer*'])"
  $PY $B/llama.cpp/convert_hf_to_gguf.py /root/src/qwen3b --outtype f16 --outfile /root/f16/qwen3b-f16.gguf
  rm -rf /root/src/qwen3b
fi
for q in Q4_K_M Q6_K Q8_0; do
  [ -f /root/quants/qwen3b-$q.gguf ] || $B/llama.cpp/build/bin/llama-quantize /root/f16/qwen3b-f16.gguf /root/quants/qwen3b-$q.gguf $q
done
cat > pc_entries.json <<'EOF'
[
 {"id": "plain-qwen3b-F16",    "role": "plain-control", "kind": "gguf", "path": "/root/f16/qwen3b-f16.gguf",     "donor": "qwen2.5-coder:3b-instruct-q4_K_M"},
 {"id": "plain-qwen3b-Q8_0",   "role": "plain-control", "kind": "gguf", "path": "/root/quants/qwen3b-Q8_0.gguf",   "donor": "qwen2.5-coder:3b-instruct-q4_K_M"},
 {"id": "plain-qwen3b-Q6_K",   "role": "plain-control", "kind": "gguf", "path": "/root/quants/qwen3b-Q6_K.gguf",   "donor": "qwen2.5-coder:3b-instruct-q4_K_M"},
 {"id": "plain-qwen3b-Q4_K_M", "role": "plain-control", "kind": "gguf", "path": "/root/quants/qwen3b-Q4_K_M.gguf", "donor": "qwen2.5-coder:3b-instruct-q4_K_M"}
]
EOF
bash start_ollama.sh
$PY run_entries.py pc_entries.json --setting base --results-dir /workspace/p2rerun/results
$PY score_runs.py /workspace/p2rerun/results
df -h / | tail -1
echo PC_DONE
