#!/usr/bin/env bash
# Start the pinned Ollama server with the census settings (idempotent).
set -euo pipefail
export OLLAMA_MODELS=/root/omodels OLLAMA_NUM_PARALLEL=1 OLLAMA_HOST=127.0.0.1:11434
if ! curl -sf http://127.0.0.1:11434/api/version >/dev/null; then
  nohup /root/p2/ollama/bin/ollama serve >> /workspace/p2rerun/logs/serve.log 2>&1 &
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done
fi
curl -s http://127.0.0.1:11434/api/version; echo
