#!/usr/bin/env bash
# P0 CPU jobs (see RUN_PLAN.md): phi3.5 library-mix rebuild (P0-f), code-calibrated imatrix (P0-d),
# perplexity (P0-e). Runs beside the GPU queue. Sources download to the network volume, F16 files
# live on local disk one model at a time.
set -uo pipefail
B=/root/p2
PY=$B/venv/bin/python
W=/workspace/p2rerun
BIN=$B/llama.cpp/build/bin
OC=$W/quants-imat-code
mkdir -p "$OC" /root/f16 "$W/src" "$W/ppl"
cmake --build "$B/llama.cpp/build" --target llama-perplexity -j 8 >/dev/null

if [ ! -f /root/calib/code.txt ]; then
  find "$B/llama.cpp" -name "*.py" -size -200k | sort | xargs cat | head -c 1500000 > /root/calib/code.txt
fi
sha256sum /root/calib/code.txt > "$W/calib_code_sha256.txt"

lib() { "$B/ollama/bin/ollama" show --modelfile "$1" | sed -n "s/^FROM //p" | grep blobs; }

f16() {  # repo rev short
  local src=$W/src/$3 out=/root/f16/$3-f16.gguf
  [ -f "$out" ] && return 0
  $PY -c "from huggingface_hub import snapshot_download; snapshot_download('$1', revision='$2', local_dir='$src', allow_patterns=['*.json','*.safetensors','*.model','*.txt','*.py','tokenizer*'])"
  $PY "$B/llama.cpp/convert_hf_to_gguf.py" "$src" --outtype f16 --outfile "$out" > /dev/null 2>&1
  rm -rf "$src"
}

ppl() {  # label path
  local log=$W/ppl/$1.log
  if ! grep -q "Final estimate" "$log" 2>/dev/null; then
    "$BIN/llama-perplexity" -m "$2" -f /root/calib/wikitext-2-raw/wiki.test.raw --chunks 20 -c 512 -t 12 > "$log" 2>&1
  fi
  echo "PPL $1 $(grep -o 'Final estimate: PPL = [0-9.]*' "$log" | tail -1)"
}

codeimat() {  # short levels...
  local short=$1; shift
  [ -f "$OC/$short.imatrix" ] || "$BIN/llama-imatrix" -m "/root/f16/$short-f16.gguf" -f /root/calib/code.txt \
    -o "$OC/$short.imatrix" --chunks 100 -c 512 -t 12 > "$W/logs/imatrix-code-$short.log" 2>&1
  for q in "$@"; do
    [ -f "$OC/$short-codeimat-$q.gguf" ] || "$BIN/llama-quantize" --imatrix "$OC/$short.imatrix" \
      "/root/f16/$short-f16.gguf" "$OC/$short-codeimat-$q.gguf" "$q" > /dev/null 2>&1
  done
}

# ---- phi3.5 ----
f16 microsoft/Phi-3.5-mini-instruct 2fe192450127e6a83f7441aef6e3ca586c338b77 phi35
LIBMIX=$W/quants/phi35-Q2_K-libmix.gguf
[ -f "$LIBMIX" ] || "$BIN/llama-quantize" --tensor-type attn_qkv=q2_k /root/f16/phi35-f16.gguf "$LIBMIX" Q2_K > "$W/logs/p0f-quantize.log" 2>&1
$PY /root/p2/run/compare_tensors.py lib-phi-q2_K="$(lib phi3.5:3.8b-mini-instruct-q2_K)" libmix-phi-Q2_K="$LIBMIX" > "$W/p0f_compare.jsonl"
python3 -c "import json; r=json.loads(open('$W/p0f_compare.jsonl').readline()); print('P0F identical', r['identical_tensors'], 'of', r['n_tensors'], 'type_differs', r['type_differs'], 'bytes_differ', r['same_type_bytes_differ'])"
codeimat phi35 Q2_K Q3_K_S Q3_K_M
ppl phi35-F16 /root/f16/phi35-f16.gguf
ppl phi35-lib-q2_K "$(lib phi3.5:3.8b-mini-instruct-q2_K)"
ppl phi35-lib-q4_K_M "$(lib phi3.5:3.8b-mini-instruct-q4_K_M)"
ppl phi35-libmix-Q2_K "$LIBMIX"
for q in Q2_K Q3_K_S Q3_K_M; do
  ppl phi35-plain-$q "$W/quants/phi35-$q.gguf"
  ppl phi35-imatwiki-$q "$W/quants-imat/phi35-imat-$q.gguf"
  ppl phi35-imatcode-$q "$OC/phi35-codeimat-$q.gguf"
done
rm -f /root/f16/phi35-f16.gguf

# ---- Qwen2.5-Coder-3B ----
f16 Qwen/Qwen2.5-Coder-3B-Instruct 488639f1ff808d1d3d0ba301aef8c11461451ec5 qwen3b
codeimat qwen3b Q2_K Q3_K_S Q3_K_M Q3_K_L
ppl qwen3b-F16 /root/f16/qwen3b-f16.gguf
ppl qwen3b-lib-q4_K_M "$(lib qwen2.5-coder:3b-instruct-q4_K_M)"
for q in q2_K q3_K_S q3_K_M q3_K_L; do ppl qwen3b-lib-$q "$(lib qwen2.5-coder:3b-instruct-$q)"; done
for q in Q4_K_M Q6_K Q8_0; do ppl qwen3b-plain-$q "$W/quants/qwen3b-$q.gguf"; done
for q in Q2_K Q3_K_S Q3_K_M Q3_K_L; do
  ppl qwen3b-imatwiki-$q "$W/quants-imat/qwen3b-imat-$q.gguf"
  ppl qwen3b-imatcode-$q "$OC/qwen3b-codeimat-$q.gguf"
done
rm -f /root/f16/qwen3b-f16.gguf
ls -la "$OC"
echo P0_CPU_DONE
