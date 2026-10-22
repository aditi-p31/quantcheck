#!/usr/bin/env python3
"""Re-score the archived census smoke transcripts with EvalPlus 0.3.1 (CPU job).

A1 found HumanEval/15 scored as failed for every census artifact although most generations contain
the standard solution. This re-scores each transcript with the same padding approach as the census
scorer and records, per artifact, the original and the new per-task results.

Usage: rescore_census.py CENSUS_RESULTS_DIR OUT.jsonl [workers]
"""
import json, os, sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_runs import score  # noqa: E402

from evalplus.data import get_human_eval_plus  # noqa: E402

TASKS = None


def work(item):
    tag, path = item
    s = score(path, TASKS)
    return {"tag": tag, "transcript": os.path.basename(path), "per_task": s,
            "n_pass": sum(s.values()) if s else None}


def main():
    global TASKS
    rdir, out, workers = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6
    TASKS = get_human_eval_plus()
    tdir = os.path.join(rdir, "transcripts")
    items = []
    for l in open(os.path.join(rdir, "audit_results.jsonl")):
        if not l.strip():
            continue
        r = json.loads(l)
        t = r.get("transcript")
        if not t:
            continue
        for cand in (t, t.replace(".jsonl", ".smoke.jsonl")):
            if os.path.exists(os.path.join(tdir, cand)):
                items.append((r["tag"], os.path.join(tdir, cand)))
                break
    done = set()
    if os.path.exists(out):
        done = {json.loads(l)["tag"] for l in open(out) if l.strip()}
    items = [i for i in items if i[0] not in done]
    print(len(items), "transcripts to re-score", flush=True)
    with Pool(workers) as pool, open(out, "a") as f:
        for i, row in enumerate(pool.imap_unordered(work, items), 1):
            f.write(json.dumps(row) + "\n")
            f.flush()
            if i % 25 == 0:
                print(f"{i}/{len(items)}", flush=True)
    print("RESCORE_DONE", flush=True)


if __name__ == "__main__":
    main()
