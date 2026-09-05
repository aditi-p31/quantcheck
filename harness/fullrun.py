#!/usr/bin/env python3
"""Full 164-task HumanEval+ evaluation for defect-suspect artifacts.

Queue: every official-channel artifact whose smoke pass rate is < 60%
of the flat screen AND whose smoke_pass <= 8 (deep suspects + cliff
cases). Generates all 164 tasks, scores with EvalPlus, writes
results/fullrun_scores.jsonl. Resumable.
"""
import glob, json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit

ROOT = os.path.dirname(HERE)
RESULTS = audit.RESULTS
EVALPLUS_BIN = os.environ.get("EVALPLUS_BIN", "/workspace/audit/venv/bin")

def full_generate(tag):
    from evalplus.data import get_human_eval_plus
    tasks = get_human_eval_plus()
    audit.TASKS = tasks
    rec = audit.audit_one({"tag": tag}, list(tasks.keys()), keep=False)
    return rec

def score_full(transcript_path):
    from evalplus.data import get_human_eval_plus
    tasks = get_human_eval_plus()
    gens = {json.loads(l)["task_id"]: json.loads(l)["solution"]
            for l in open(transcript_path) if l.strip()}
    with tempfile.TemporaryDirectory() as td:
        spath = os.path.join(td, "samples.jsonl")
        with open(spath, "w") as f:
            for tid in tasks:
                f.write(json.dumps({"task_id": tid,
                                    "solution": gens.get(tid, "pass")}) + "\n")
        env = dict(os.environ, PATH=os.environ["PATH"] + ":" + EVALPLUS_BIN)
        subprocess.run([os.path.join(EVALPLUS_BIN, "evalplus.sanitize"),
                        "--samples", spath], capture_output=True, env=env)
        san = spath.replace(".jsonl", "-sanitized.jsonl")
        if not os.path.exists(san):
            san = spath
        subprocess.run([os.path.join(EVALPLUS_BIN, "evalplus.evaluate"),
                        "--dataset", "humaneval", "--samples", san],
                       capture_output=True, text=True, env=env, timeout=3600)
        rf = glob.glob(os.path.join(td, "*eval_results.json"))
        if not rf:
            return None
        ev = json.load(open(rf[0]))["eval"]
        n_pass = 0
        for tid, entries in ev.items():
            e = entries[0] if isinstance(entries, list) else entries
            if e.get("base_status") == "pass" and e.get("plus_status") == "pass":
                n_pass += 1
        return n_pass

def main():
    scored = [json.loads(l) for l in open(os.path.join(RESULTS, "audit_scored.jsonl")) if l.strip()]
    defects = [r["tag"] for r in scored
               if r.get("channel") == "ollama-official" and r["smoke_pass"] <= 2
               and r["verdict"] == "DEFECTIVE"]
    # degradation map: one representative (lowest-scoring quant) per family+size
    import re
    def fk(t):
        m = re.match(r"([^:]+):([\d.]+b)", t); return (m.group(1), m.group(2)) if m else (t,"?")
    collapse = {}
    for r in scored:
        if r.get("channel") == "ollama-official" and 2 < r["smoke_pass"] <= 8:
            k = fk(r["tag"])
            if k not in collapse or r["smoke_pass"] < collapse[k][1]:
                collapse[k] = (r["tag"], r["smoke_pass"])
    queue = defects + [v[0] for v in collapse.values()]
    out_path = os.path.join(RESULTS, "fullrun_scores.jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["tag"] for l in open(out_path) if l.strip()}
    todo = [t for t in queue if t not in done]
    print(f"full-run queue: {len(todo)} artifacts", flush=True)
    with open(out_path, "a") as f:
        for i, tag in enumerate(todo, 1):
            t0 = time.time()
            safe = tag.replace(":", "_").replace("/", "_") + ".jsonl"
            smoke = os.path.join(RESULTS, "transcripts", safe)
            bak = smoke.replace(".jsonl", ".smoke.jsonl")
            if os.path.exists(smoke) and not os.path.exists(bak):
                import shutil; shutil.copy(smoke, bak)
            rec = full_generate(tag)
            row = {"tag": tag, "gen_error": rec.get("error")}
            tp = rec.get("transcript")
            if tp:
                # avoid clobbering smoke transcript: rename full transcript
                src = os.path.join(RESULTS, "transcripts", tp)
                dst = os.path.join(RESULTS, "transcripts",
                                   tp.replace(".jsonl", ".full164.jsonl"))
                os.replace(src, dst)
                row["full_pass"] = score_full(dst)
                row["full_n"] = 164
            row["wall_s"] = round(time.time() - t0, 1)
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"  [{i}/{len(todo)}] {tag}: {row.get('full_pass')}/164", flush=True)

if __name__ == "__main__":
    main()
