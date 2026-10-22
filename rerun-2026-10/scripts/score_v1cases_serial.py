#!/usr/bin/env python3
"""Serially score the two v1-audit closure runs (all 164 HumanEval+ tasks), as score_runs.py does,
but with EvalPlus restricted to one worker so no test runs under parallel load.
Usage: /usr/bin/python3 score_v1cases_serial.py <results-v1cases dir>"""
import glob, json, os, subprocess, sys, tempfile

from evalplus.data import get_human_eval_plus

BIN = os.path.expanduser(os.environ.get("EVALPLUS_BIN", "~/Library/Python/3.9/bin"))


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
        r = subprocess.run([os.path.join(BIN, "evalplus.evaluate"), "--dataset", "humaneval", "--samples", san,
                            "--parallel", "1"], capture_output=True, text=True, timeout=7200)
        res = glob.glob(os.path.join(td, "*eval_results.json"))
        if not res:
            raise RuntimeError(r.stderr[-2000:])
        ev = json.load(open(res[0]))["eval"]
    out = {}
    for tid in gens:
        entries = ev.get(tid)
        e = (entries[0] if isinstance(entries, list) else entries) if entries else {}
        out[tid] = e.get("base_status") == "pass" and e.get("plus_status") == "pass"
    return out


def main():
    rdir = sys.argv[1]
    tasks = get_human_eval_plus()
    runs = [json.loads(l) for l in open(os.path.join(rdir, "runs.jsonl")) if l.strip()]
    with open(os.path.join(rdir, "scored_serial.jsonl"), "w") as f:
        for r in runs:
            if r.get("error") or not r.get("transcript"):
                continue
            per = score(os.path.join(rdir, "transcripts", r["transcript"]), tasks)
            rec = {"id": r["id"], "tag": r.get("tag"), "setting": r["setting"], "blob": r.get("blob"),
                   "n_pass": sum(per.values()), "n": len(per), "per_task": per}
            f.write(json.dumps(rec) + "\n")
            print(r["id"], rec["n_pass"], "/", rec["n"], flush=True)


if __name__ == "__main__":
    main()
