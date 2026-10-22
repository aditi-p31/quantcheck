#!/usr/bin/env bash
# Pod setup for the 2026-10 rerun (see ../../run-plan/RUN_PLAN.md).
# Heavy files live on the local container disk (/root); results, hashes and logs on /workspace.
set -euo pipefail
B=/root/p2
W=/workspace/p2rerun
LLAMA_TAG=${LLAMA_TAG:-v0.7.0}
mkdir -p "$B" "$W/logs" /root/omodels

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq zstd tmux rsync >/dev/null

# Ollama 0.32.6, pinned to the census version
if [ ! -x "$B/ollama/bin/ollama" ]; then
  mkdir -p "$B/ollama"
  curl -fsSL --retry 3 -o "$B/ollama.tar.zst" \
    https://github.com/ollama/ollama/releases/download/v0.32.6/ollama-linux-amd64.tar.zst
  sha256sum "$B/ollama.tar.zst" > "$W/ollama_tarball.sha256"
  tar --zstd -xf "$B/ollama.tar.zst" -C "$B/ollama"
  rm "$B/ollama.tar.zst"
fi

# Python env: reuse the image's torch for the converter
if [ ! -x "$B/venv/bin/python" ]; then
  python3 -m venv --system-site-packages "$B/venv"
fi
"$B/venv/bin/pip" install -q evalplus==0.3.1 huggingface_hub hf_transfer sentencepiece safetensors protobuf "transformers>=4.45"

# llama.cpp at a recorded tag, CPU-only build (quantization needs no GPU)
if [ ! -d "$B/llama.cpp" ]; then
  git clone -q --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp "$B/llama.cpp"
fi
cmake -S "$B/llama.cpp" -B "$B/llama.cpp/build" -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$B/llama.cpp/build" --target llama-quantize -j 12 >/dev/null
"$B/venv/bin/pip" install -q "$B/llama.cpp/gguf-py"

# Prefetch the EvalPlus datasets so runs never depend on the network mid-way
"$B/venv/bin/python" -c "from evalplus.data import get_human_eval_plus, get_mbpp_plus; print(len(get_human_eval_plus()), len(get_mbpp_plus()))"

# Record the environment
{
  echo "date: $(date -u +%FT%TZ)"
  echo "ollama: $("$B/ollama/bin/ollama" --version 2>&1 | tail -1)"
  echo "llama.cpp tag: $LLAMA_TAG commit: $(git -C "$B/llama.cpp" rev-parse HEAD)"
  echo "python: $(python3 --version)"
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
} > "$W/env.txt"
"$B/venv/bin/pip" freeze > "$W/pip_freeze.txt"
cat "$W/env.txt"
echo SETUP_DONE
