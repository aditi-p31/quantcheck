#!/usr/bin/env bash
# G1-lite (see RUN_PLAN.md): Qwen2.5-Coder 0.5B and 1.5B at q2_K..q3_K_L. Library vs plain rebuild
# (tensor comparison) and library / plain / own-imatrix smoke scores in one session.
set -uo pipefail
cd /root/p2/run
B=/root/p2
PY=$B/venv/bin/python
BIN=$B/llama.cpp/build/bin
W=/workspace/p2rerun
G=$W/quants-g1
mkdir -p "$G" /root/f16 "$W/src"
bash start_ollama.sh
LEVELS="q2_K q3_K_S q3_K_M q3_K_L"
lib() { "$B/ollama/bin/ollama" show --modelfile "$1" | sed -n "s/^FROM //p" | grep blobs; }

for size in 0.5b 1.5b; do
  short=qwen$size
  case $size in 0.5b) repo=Qwen/Qwen2.5-Coder-0.5B-Instruct ;; 1.5b) repo=Qwen/Qwen2.5-Coder-1.5B-Instruct ;; esac
  rev=$($PY -c "from huggingface_hub import HfApi; print(HfApi().model_info('$repo').sha)")
  echo "{\"repo\": \"$repo\", \"revision\": \"$rev\"}" >> "$W/source_commits.jsonl"
  f16=/root/f16/$short-f16.gguf
  if [ ! -f "$f16" ]; then
    $PY -c "from huggingface_hub import snapshot_download; snapshot_download('$repo', revision='$rev', local_dir='$W/src/$short', allow_patterns=['*.json','*.safetensors','*.txt','tokenizer*'])"
    $PY "$B/llama.cpp/convert_hf_to_gguf.py" "$W/src/$short" --outtype f16 --outfile "$f16" > /dev/null 2>&1
    rm -rf "$W/src/$short"
  fi
  [ -f "$G/$short.imatrix" ] || "$BIN/llama-imatrix" -m "$f16" -f /root/calib/wikitext-2-raw/wiki.train.raw \
    -o "$G/$short.imatrix" --chunks 100 -c 512 -t 12 > "$W/logs/imatrix-$short.log" 2>&1
  for q in $LEVELS; do
    Q=$(echo $q | tr a-z A-Z | sed 's/_K_/_K_/')
    [ -f "$G/$short-plain-$q.gguf" ] || "$BIN/llama-quantize" "$f16" "$G/$short-plain-$q.gguf" "$Q" > /dev/null 2>&1
    [ -f "$G/$short-imat-$q.gguf" ] || "$BIN/llama-quantize" --imatrix "$G/$short.imatrix" "$f16" "$G/$short-imat-$q.gguf" "$Q" > /dev/null 2>&1
    tag=qwen2.5-coder:$size-instruct-$q
    for a in 1 2 3 4; do "$B/ollama/bin/ollama" pull "$tag" > /dev/null 2>&1 && break; sleep $((30 * a)); done
    $PY compare_tensors.py "lib-$short-$q=$(lib $tag)" "plain-$short-$q=$G/$short-plain-$q.gguf" >> "$W/g1_tensor_compare.jsonl"
  done
  rm -f "$f16"
done
python3 -c "
import json
for l in open('$W/g1_tensor_compare.jsonl'):
    r = json.loads(l); print('G1CMP', r['a'], 'identical', r['identical_tensors'], 'of', r['n_tensors'], 'type_differs', r['type_differs'], 'bytes_differ', r['same_type_bytes_differ'])
"

$PY - <<'EOF'
import json
G = "/workspace/p2rerun/quants-g1"
E = []
for size in ("0.5b", "1.5b"):
    donor = f"qwen2.5-coder:{size}-instruct-q4_K_M"
    for q in ("q2_K", "q3_K_S", "q3_K_M", "q3_K_L"):
        E.append({"id": f"g1lib-qwen{size}-{q}", "role": "library", "kind": "ollama", "tag": f"qwen2.5-coder:{size}-instruct-{q}"})
        E.append({"id": f"g1plain-qwen{size}-{q}", "role": "plain", "kind": "gguf", "path": f"{G}/qwen{size}-plain-{q}.gguf", "donor": donor})
        E.append({"id": f"g1imat-qwen{size}-{q}", "role": "own-imatrix", "kind": "gguf", "path": f"{G}/qwen{size}-imat-{q}.gguf", "donor": donor})
json.dump(E, open("g1_entries.json", "w"), indent=1)
print(len(E), "G1 entries")
EOF
$PY run_entries.py g1_entries.json --setting base --results-dir $W/results-g1
echo G1_GEN_DONE
$PY score_runs.py $W/results-g1 6
df -h / | tail -1
echo G1_DONE
