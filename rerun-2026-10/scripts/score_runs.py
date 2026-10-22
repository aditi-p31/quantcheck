#!/usr/bin/env python3
"""Score run transcripts with EvalPlus (HumanEval+), as harness/score_smoke.py does.

EvalPlus needs a complete 164-task sample file, so each transcript is padded with failing
placeholders and only the attempted tasks are read back. A task passes only when both the base
and plus tests pass. Writes scored.jsonl next to runs.jsonl; resumable on (id, setting).
"""
import glob, json, os, subprocess, sys, tempfile

from evalplus.data import get_human_eval_plus

BIN = os.path.dirname(sys.executable)


def score(tpath, tasks):
    gens = {}
    for l in open(tpath):
        if l.strip():
            g = json.loads(l)
            gens[g["task_id"]] = g["solution"]
    with tempfile.TemporaryDirectory() as td:
        spath = os.path.join(td, "samples.jsonl")
        with open(spath, "w") as f:
            for tid in tasks:
                f.write(json.dumps({"task_id": tid, "solution": gens.get(tid, "pass  # placeholder-unattempted")}) + "\n")
        subprocess.run([os.path.join(BIN, "evalplus.sanitize"), "--samples", spath], capture_output=True)
        san = spath.replace(".jsonl", "-sanitized.jsonl")
        if not os.path.exists(san):
            san = spath
        subprocess.run([os.path.join(BIN, "evalplus.evaluate"), "--dataset", "humaneval", "--samples", san],
                       capture_output=True, text=True, timeout=1800)
        res = glob.glob(os.path.join(td, "*eval_results.json"))
        if not res:
            return None
        ev = json.load(open(res[0]))["eval"]
    out = {}
    for tid in gens:
        entries = ev.get(tid)
        e = (entries[0] if isinstance(entries, list) else entries) if entries else {}
        out[tid] = e.get("base_status") == "pass" and e.get("plus_status") == "pass"
    return out


_TASKS = None


def _score_one(args):
    rdir, r = args
    return r, score(os.path.join(rdir, "transcripts", r["transcript"]), _TASKS)


def main():
    global _TASKS
    rdir = sys.argv[1] if len(sys.argv) > 1 else "/workspace/p2rerun/results"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if not os.path.exists(os.path.join(rdir, "runs.jsonl")):
        return
    _TASKS = get_human_eval_plus()
    runs = [json.loads(l) for l in open(os.path.join(rdir, "runs.jsonl")) if l.strip()]
    out_path = os.path.join(rdir, "scored.jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {(r["id"], r["setting"]) for r in map(json.loads, filter(str.strip, open(out_path)))}
    todo = [r for r in runs if (r["id"], r["setting"]) not in done and not r.get("error") and r.get("transcript")]
    if not todo:
        return
    from multiprocessing import Pool
    with Pool(workers) as pool, open(out_path, "a") as f:
        for r, s in pool.imap_unordered(_score_one, [(rdir, r) for r in todo]):
            key = (r["id"], r["setting"])
            if s is None:
                print(f"{key}: SCORING FAILED", flush=True)
                continue
            row = {"id": r["id"], "setting": r["setting"], "kind": r["kind"], "role": r.get("role"),
                   "tag": r.get("tag") or r.get("file") or r.get("path"), "n_pass": sum(s.values()),
                   "n": len(s), "trunc_frac": r.get("trunc_frac"), "per_task": s}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"{r['id']:<28} {r['setting']:<10} {row['n_pass']}/{row['n']}", flush=True)


if __name__ == "__main__":
    main()
