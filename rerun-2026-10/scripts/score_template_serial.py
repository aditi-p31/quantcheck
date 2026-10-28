#!/usr/bin/env python3
"""Serially score the template-test runs (15-task screen and all 164 HumanEval+ tasks) with EvalPlus
0.3.1 restricted to one worker, as rerun-2026-10/scripts/score_v1cases_serial.py does for the closure run.
Usage: /usr/bin/python3 score_template_serial.py <rerun-2026-10/results-tpl dir>
Writes <results dir>/scored_serial.jsonl and prints a summary table."""
import glob, json, os, subprocess, sys, tempfile

from evalplus.data import get_human_eval_plus

BIN = os.path.expanduser(os.environ.get("EVALPLUS_BIN", "~/Library/Python/3.9/bin"))
SUITE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "smoke_suite_v1.json")))["suite_tasks"]


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
    rows = []
    with open(os.path.join(rdir, "scored_serial.jsonl"), "w") as f:
        for r in runs:
            if r.get("error") or not r.get("transcript"):
                continue
            per = score(os.path.join(rdir, "transcripts", r["transcript"]), tasks)
            sub = sum(1 for t in SUITE if per.get(t))
            rec = {"id": r["id"], "setting": r["setting"], "modelfile_mode": r.get("modelfile_mode"),
                   "file_sha256": r.get("file_sha256"), "n_pass": sum(per.values()), "n": len(per),
                   "screen_subset_pass": sub, "trunc_frac": r.get("trunc_frac"), "per_task": per}
            f.write(json.dumps(rec) + "\n")
            rows.append(rec)
            print(f"{r['id']:32s} {r['setting']:8s} {rec['n_pass']:4d} / {rec['n']:3d}   trunc {r.get('trunc_frac')}", flush=True)
    print()
    print(f"{'file / condition':34s} {'screen':>8s} {'164':>8s} {'trunc15':>8s} {'trunc164':>9s}")
    for fid in ("Q3_K_M", "Q4_K_M"):
        for mode in ("fromonly", "metaltpl", "donor"):
            rid = f"tb-ds67-{fid}-{mode}"
            s = next((x for x in rows if x["id"] == rid and x["setting"] == "screen"), None)
            l = next((x for x in rows if x["id"] == rid and x["setting"] == "full164"), None)
            print(f"{rid:34s} {s['n_pass'] if s else '-':>8} {l['n_pass'] if l else '-':>8} "
                  f"{s['trunc_frac'] if s else '-':>8} {l['trunc_frac'] if l else '-':>9}")


if __name__ == "__main__":
    main()
