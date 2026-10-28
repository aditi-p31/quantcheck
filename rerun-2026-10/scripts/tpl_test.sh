#!/usr/bin/env bash
# Template test for the two TheBloke deepseek-coder-6.7B files (2026-10-28), one RTX 4090 pod.
# Same Ollama release as the census (0.32.6) from the October pods' archive (tarball sha256 dec2fa50...), census options,
# EvalPlus 0.3.1 task prompts. Downloads the two files and checks them against the census digests
# (rerun-2026-10/serial/census_digests.json, file_sha256), then runs run_template_test.py.
# Scoring is done afterwards on the Mac, serially. Results, logs and hashes go to /workspace/p2tpl.
set -euo pipefail
B=/root/p2
W=/workspace/p2tpl
RUN=$B/run
mkdir -p "$B" "$W/logs" "$W/results" /root/omodels /root/hfdl
export DEBIAN_FRONTEND=noninteractive

if [ ! -x "$B/ollama/bin/ollama" ]; then
  apt-get update -qq && apt-get install -y -qq zstd xz-utils >/dev/null
  mkdir -p "$B/ollama"
  curl -fsSL --retry 3 -o "$B/ollama.tar.zst" \
    https://github.com/ollama/ollama/releases/download/v0.32.6/ollama-linux-amd64.tar.zst
  sha256sum "$B/ollama.tar.zst" > "$W/ollama_tarball_tpl.sha256"
  grep -q '^dec2fa50d24e6868ca3c4c977d69d059399372105f951a9acc320a5a79aadcfc ' "$W/ollama_tarball_tpl.sha256" \
    || { echo "OLLAMA TARBALL HASH MISMATCH"; cat "$W/ollama_tarball_tpl.sha256"; exit 1; }
  tar --zstd -xf "$B/ollama.tar.zst" -C "$B/ollama"
  rm "$B/ollama.tar.zst"
fi
if [ ! -x "$B/venv/bin/python" ]; then
  python3 -m venv --system-site-packages "$B/venv"
fi
"$B/venv/bin/pip" install -q evalplus==0.3.1 gguf
"$B/venv/bin/python" -c "from evalplus.data import get_human_eval_plus; print(len(get_human_eval_plus()))"

# the two files, checked against the census digests
dl() {  # url, file, expected sha256
  local f="/root/hfdl/$2"
  if [ ! -f "$f" ]; then curl -fsSL --retry 4 --retry-delay 30 -o "$f" "$1"; fi
  local h; h=$(sha256sum "$f" | cut -d' ' -f1)
  echo "$h  $2" >> "$W/file_sha256.txt"
  [ "$h" = "$3" ] || { echo "FILE HASH MISMATCH $2: $h != $3"; exit 1; }
}
: > "$W/file_sha256.txt"
dl https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q3_K_M.gguf \
   deepseek-coder-6.7b-instruct.Q3_K_M.gguf 6c841fde94b9103c92e875c9ab0ebeeb624b0709b2410c3bd942c80cd635117f
dl https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf \
   deepseek-coder-6.7b-instruct.Q4_K_M.gguf 92da6238854f2fa902d8b2ad79d548536af1d3ab06821f323bd5bbcea2013276
cat "$W/file_sha256.txt"

{ date -u; nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; "$B/ollama/bin/ollama" --version; python3 --version; } \
  > "$W/env_tpl.txt" 2>&1
"$B/venv/bin/pip" freeze > "$W/pip_freeze_tpl.txt"
cat "$W/env_tpl.txt"

# Ollama server with the census settings, logging to this run's folder
# The client (harness/audit.py) builds URLs from OLLAMA_HOST, so it needs the scheme. The first launch on
# 2026-10-28 exported the host without it, every /api/chat call failed (results-tpl/aborted_first_attempt/),
# and run_template_test.py was relaunched by hand with OLLAMA_HOST=http://127.0.0.1:11434 on the same
# server, files and donor pull (results-tpl/tpl.log).
export OLLAMA_MODELS=/root/omodels OLLAMA_NUM_PARALLEL=1 OLLAMA_HOST=http://127.0.0.1:11434
if ! curl -sf http://127.0.0.1:11434/api/version >/dev/null; then
  nohup "$B/ollama/bin/ollama" serve >> "$W/logs/serve.log" 2>&1 &
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done
fi
curl -s http://127.0.0.1:11434/api/version; echo

# the donor tag's Modelfile, recorded as pulled
"$B/ollama/bin/ollama" pull deepseek-coder:6.7b-instruct-q4_K_M
"$B/ollama/bin/ollama" show --modelfile deepseek-coder:6.7b-instruct-q4_K_M > "$W/donor_modelfile.txt"
"$B/ollama/bin/ollama" show --template deepseek-coder:6.7b-instruct-q4_K_M > "$W/donor_template.txt"

cd "$RUN"
OLLAMA_BIN="$B/ollama/bin/ollama" "$B/venv/bin/python" run_template_test.py tpl_entries.json --results-dir "$W/results" 2>&1 | tee -a "$W/logs/tpl.log"
xz -k -f "$W/logs/serve.log"
grep -c . "$W/results/runs.jsonl"
echo TPL_DONE
