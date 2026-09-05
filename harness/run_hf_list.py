#!/usr/bin/env python3
"""Run hf_audit.audit_hf over a JSON list file. Proper script (no inline
shell-python quoting). Usage: run_hf_list.py <list.json>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf_audit, audit
from evalplus.data import get_human_eval_plus

def main(list_path):
    audit.TASKS = get_human_eval_plus()
    entries = json.load(open(list_path))["artifacts"]
    out_path = os.path.join(audit.RESULTS, "audit_results.jsonl")
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            if l.strip():
                r = json.loads(l)
                if not r.get("skip") and not r.get("error"):
                    done.add(r["tag"])
    with open(out_path, "a") as f:
        for e in entries:
            if e["tag"] in done:
                print("skip", e["tag"]); continue
            try:
                rec = hf_audit.audit_hf(e, audit.SUITE)
            except Exception as ex:
                rec = dict(e); rec["error"] = f"{type(ex).__name__}: {ex}"[:200]
            f.write(json.dumps(rec) + "\n"); f.flush()
            print(e["tag"], "ok" if not rec.get("error") else "ERR " + rec["error"][:80], flush=True)

if __name__ == "__main__":
    main(sys.argv[1])
