#!/usr/bin/env python3
"""Print one line per run: score, tensor hash, file hash and key GGUF metadata."""
import json, os, sys

rdir = sys.argv[1] if len(sys.argv) > 1 else "/workspace/p2rerun/results"
scores = {}
if os.path.exists(os.path.join(rdir, "scored.jsonl")):
    for l in open(os.path.join(rdir, "scored.jsonl")):
        if l.strip():
            r = json.loads(l)
            scores[(r["id"], r["setting"])] = f"{r['n_pass']}/{r['n']}"
for l in open(os.path.join(rdir, "runs.jsonl")):
    if not l.strip():
        continue
    r = json.loads(l)
    h = r.get("hash") or {}
    meta = h.get("meta", {})
    print(f"{r['id']:<22} {r['setting']:<9} {scores.get((r['id'], r['setting']), '?'):>6}  "
          f"tensor={h.get('tensor_sha256', '')[:12]}  file={h.get('file_sha256', '')[:12]}  "
          f"n={h.get('n_tensors')}  ft={meta.get('general.file_type')}  "
          f"name={meta.get('general.name')}/{meta.get('general.finetune')}  imat={h.get('imatrix_keys')}"
          + (f"  ERR={r['error'][:60]}" if r.get("error") else ""))
