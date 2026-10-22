#!/usr/bin/env bash
# Close the two uncertified miss-audit cases (review round 2, 2026-10-21).
# Runs all 164 HumanEval+ tasks on CUDA, Ollama 0.32.6, census options, for the two v1-audit tags whose
# audit run left no backend/digest record. The run records each tag's blob digest (Modelfile FROM line),
# which must equal the census digest:
#   granite-code:3b-instruct-q3_K_M  sha256-9c66e1aac6105389b7d3cc47ac70e79f285c3a7fa1595fc53020f118c8893ee5
#   mistral:7b-instruct-q3_K_S       sha256-067ecc276050c06039eee72517e53c5b73fdba46105e0a4df48445c2fe7b04d8
# Scoring is done afterwards on the Mac, serially, with the paper's serial scorer.
set -euo pipefail
B=/root/p2
W=/workspace/p2rerun
mkdir -p "$B" "$W/logs" /root/omodels

if [ ! -x "$B/ollama/bin/ollama" ]; then
  apt-get update -qq && apt-get install -y -qq zstd >/dev/null
  mkdir -p "$B/ollama"
  curl -fsSL --retry 3 -o "$B/ollama.tar.zst" \
    https://github.com/ollama/ollama/releases/download/v0.32.6/ollama-linux-amd64.tar.zst
  sha256sum "$B/ollama.tar.zst" > "$W/ollama_tarball_v1cases.sha256"
  tar --zstd -xf "$B/ollama.tar.zst" -C "$B/ollama"
  rm "$B/ollama.tar.zst"
fi
if [ ! -x "$B/venv/bin/python" ]; then
  python3 -m venv --system-site-packages "$B/venv"
fi
"$B/venv/bin/pip" install -q evalplus==0.3.1
"$B/venv/bin/python" -c "from evalplus.data import get_human_eval_plus; print(len(get_human_eval_plus()))"

{ date -u; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader; "$B/ollama/bin/ollama" --version; } \
  > "$W/env_v1cases.txt" 2>&1

bash "$B/run/start_ollama.sh"

cd "$B/run"
cat > v1cases_entries.json <<'EOF'
[
 {"id": "v1fn-granite-code_3b-instruct-q3_K_M", "role": "v1-audit-closure", "kind": "ollama", "tag": "granite-code:3b-instruct-q3_K_M"},
 {"id": "v1fn-mistral_7b-instruct-q3_K_S", "role": "v1-audit-closure", "kind": "ollama", "tag": "mistral:7b-instruct-q3_K_S"}
]
EOF
"$B/venv/bin/python" run_entries.py v1cases_entries.json --setting full164 --tasks all164.json \
  --results-dir "$W/results-v1cases" --no-hash
grep -o '"blob": "[^"]*"' "$W/results-v1cases/runs.jsonl"
echo V1CASES_DONE
