#!/usr/bin/env python3
"""Score smoke transcripts with EvalPlus and attach verdicts.

EvalPlus's evaluator requires a complete 164-task sample file, so each
15-task transcript is padded with failing placeholders for the remaining
tasks; only the suite tasks' results are read back.

Writes results/audit_scored.jsonl (one line per artifact: smoke pass rate,
features, verdict). Verdict rule (DESIGN.md): flag if suite pass rate < 60%.
"""
import glob, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
SUITE = set(json.load(open(os.path.join(ROOT, "smoke_suite_v1.json")))["suite_tasks"])
EVALPLUS_BIN = os.environ.get("EVALPLUS_BIN", os.path.expanduser("~/Library/Python/3.9/bin"))

def score_transcript(tpath):
    from evalplus.data import get_human_eval_plus
    tasks = get_human_eval_plus()
    gens = {json.loads(l)["task_id"]: json.loads(l)["solution"] for l in open(tpath) if l.strip()}
    with tempfile.TemporaryDirectory() as td:
        spath = os.path.join(td, "samples.jsonl")
        with open(spath, "w") as f:
            for tid in tasks:
                sol = gens.get(tid, "pass  # placeholder-unattempted")
                f.write(json.dumps({"task_id": tid, "solution": sol}) + "\n")
        env = dict(os.environ, PATH=os.environ["PATH"] + ":" + EVALPLUS_BIN)
        subprocess.run([os.path.join(EVALPLUS_BIN, "evalplus.sanitize"), "--samples", spath],
                       capture_output=True, env=env)
        san = spath.replace(".jsonl", "-sanitized.jsonl")
        if not os.path.exists(san):
            san = spath
        r = subprocess.run([os.path.join(EVALPLUS_BIN, "evalplus.evaluate"),
                            "--dataset", "humaneval", "--samples", san],
                           capture_output=True, text=True, env=env, timeout=1800)
        res_files = glob.glob(os.path.join(td, "*eval_results.json"))
        if not res_files:
            return None
        ev = json.load(open(res_files[0]))["eval"]
        out = {}
        for tid in SUITE:
            entries = ev.get(tid)
            if not entries:
                out[tid] = False; continue
            e = entries[0] if isinstance(entries, list) else entries
            out[tid] = (e.get("base_status") == "pass" and e.get("plus_status") == "pass")
        return out

def main():
    audit = [json.loads(l) for l in open(os.path.join(RESULTS, "audit_results.jsonl")) if l.strip()]
    out_path = os.path.join(RESULTS, "audit_scored.jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["tag"] for l in open(out_path) if l.strip()}
    with open(out_path, "a") as f:
        for rec in audit:
            if rec["tag"] in done or rec.get("error") or rec.get("skip") or not rec.get("transcript"):
                continue
            tp = os.path.join(RESULTS, "transcripts", rec["transcript"])
            scores = score_transcript(tp)
            if scores is None:
                print(f"{rec['tag']}: SCORING FAILED"); continue
            n_pass = sum(scores.values())
            row = {"tag": rec["tag"], "family": rec.get("family"), "quant": rec.get("quant"),
                   "params_b": rec.get("params_b"), "channel": rec.get("channel"),
                   "smoke_pass": n_pass, "smoke_n": len(scores),
                   "smoke_rate": round(n_pass / len(scores), 3),
                   "verdict": "DEFECTIVE" if n_pass / len(scores) < 0.6 else "healthy",
                   "trunc_frac": rec.get("trunc_frac"), "echo_frac_mean": rec.get("echo_frac_mean"),
                   "rep6_share_mean": rec.get("rep6_share_mean"), "def_frac": rec.get("def_frac"),
                   "per_task": scores}
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"{rec['tag']}: {n_pass}/{len(scores)} -> {row['verdict']}")

if __name__ == "__main__":
    main()
