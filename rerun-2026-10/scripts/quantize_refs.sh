#!/usr/bin/env bash
# R1: build plain referees from the original checkpoints. No --imatrix, no AWQ.
# One model at a time so the local disk never holds both checkpoints.
set -euo pipefail
B=/root/p2
W=/workspace/p2rerun
Q=/root/quants
mkdir -p "$Q" /root/src /root/f16
export HF_HUB_ENABLE_HF_TRANSFER=1

build() {
  local repo=$1 short=$2; shift 2
  local src=/root/src/$short f16=/root/f16/$short-f16.gguf
  "$B/venv/bin/python" - "$repo" "$src" "$W/source_commits.jsonl" <<'EOF'
import json, sys
from huggingface_hub import HfApi, snapshot_download
repo, dest, log = sys.argv[1:4]
sha = HfApi().model_info(repo).sha
snapshot_download(repo, revision=sha, local_dir=dest,
                  allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "*.py", "tokenizer*"])
open(log, "a").write(json.dumps({"repo": repo, "revision": sha}) + "\n")
print(repo, sha)
EOF
  "$B/venv/bin/python" "$B/llama.cpp/convert_hf_to_gguf.py" "$src" --outtype f16 --outfile "$f16"
  for q in "$@"; do
    "$B/llama.cpp/build/bin/llama-quantize" "$f16" "$Q/$short-$q.gguf" "$q"
  done
  rm -rf "$src" "$f16"
}

build Qwen/Qwen2.5-Coder-3B-Instruct qwen3b Q2_K Q3_K_S Q3_K_M Q3_K_L
build microsoft/Phi-3.5-mini-instruct phi35 Q2_K Q3_K_S Q3_K_M
ls -la "$Q"
echo QUANTIZE_DONE
