#!/usr/bin/env bash
# R5 preparation (CPU only, runs alongside the GPU queue): our own importance matrix from the same
# source checkpoints and llama.cpp commit as the plain referees, then imatrix quants.
set -euo pipefail
B=/root/p2
PY=$B/venv/bin/python
W=/workspace/p2rerun
OUT=$W/quants-imat
mkdir -p "$OUT" /root/src /root/f16 /root/calib
cmake --build "$B/llama.cpp/build" --target llama-imatrix -j 12 >/dev/null

# Calibration text: WikiText-2 raw, train split (llama.cpp's standard choice)
if [ ! -f /root/calib/wiki.train.raw ]; then
  curl -fsSL -o /root/calib/wt2.zip https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip
  (cd /root/calib && unzip -q -o wt2.zip && cp wikitext-2-raw/wiki.train.raw . )
fi
sha256sum /root/calib/wiki.train.raw > "$W/calib_sha256.txt"

build() {
  local repo=$1 rev=$2 short=$3; shift 3
  local src=/root/src/$short f16=/root/f16/$short-f16.gguf
  if [ ! -f "$OUT/$short.imatrix" ]; then
    $PY -c "from huggingface_hub import snapshot_download; snapshot_download('$repo', revision='$rev', local_dir='$src', allow_patterns=['*.json','*.safetensors','*.model','*.txt','*.py','tokenizer*'])"
    $PY "$B/llama.cpp/convert_hf_to_gguf.py" "$src" --outtype f16 --outfile "$f16"
    rm -rf "$src"
    "$B/llama.cpp/build/bin/llama-imatrix" -m "$f16" -f /root/calib/wiki.train.raw -o "$OUT/$short.imatrix" \
      --chunks 100 -c 512 -t 12 > "$W/logs/imatrix-$short.log" 2>&1
  fi
  for q in "$@"; do
    [ -f "$OUT/$short-imat-$q.gguf" ] || "$B/llama.cpp/build/bin/llama-quantize" --imatrix "$OUT/$short.imatrix" \
      "$f16" "/root/f16/$short-imat-$q.gguf" "$q" > /dev/null 2>&1
    mv -f "/root/f16/$short-imat-$q.gguf" "$OUT/" 2>/dev/null || true
  done
  rm -f "$f16"
}

build Qwen/Qwen2.5-Coder-3B-Instruct 488639f1ff808d1d3d0ba301aef8c11461451ec5 qwen3b Q2_K Q3_K_S Q3_K_M Q3_K_L
build microsoft/Phi-3.5-mini-instruct 2fe192450127e6a83f7441aef6e3ca586c338b77 phi35 Q2_K Q3_K_S Q3_K_M
ls -la "$OUT"
echo IMATRIX_DONE
