#!/usr/bin/env python3
"""Template test for the two TheBloke deepseek-coder-6.7B community files (2026-10-28).

The census ran Hugging Face community files with no TEMPLATE line in the Modelfile (harness/hf_audit.py
copies a template only for families in its TEMPLATE_DONOR table, and the community entries' family is
"mixed"), while the Metal replication (harness/mac_night.py) supplied the deepseek-coder instruction
template. This script runs both files on one CUDA pod under three Modelfiles, so that template and
backend are no longer confounded:

  from-only       FROM <file>                                  the census condition
  metal-template  FROM <file> + TEMPLATE of harness/mac_night.py  the Metal replication's condition
  donor           the Modelfile of deepseek-coder:6.7b-instruct-q4_K_M as run_entries.donor_modelfile
                  copies it; that function drops lines beginning with '#', so the copied TEMPLATE keeps
                  the SYSTEM prompt but loses the '### Instruction:' and '### Response:' lines

Generation path, options and output statistics are those of the census (harness/audit.py via
run_entries.py). Each entry runs the 15-task screen and all 164 HumanEval+ tasks. Scoring is done
afterwards on the Mac, serially.

Usage: run_template_test.py ENTRIES.json --results-dir DIR [--only ID]
Entries: {"id", "kind": "gguf", "path", "modelfile": "from-only"|"metal-template"|"donor", "donor"?}
Resumable: (id, setting) pairs already in runs.jsonl are skipped.
"""
import argparse, hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "harness"))
import audit
import run_entries as R

# Verbatim from harness/mac_night.py (DEEPSEEK_TPL), the template the Metal replication supplied.
METAL_TEMPLATE = '{{ .System }}\n### Instruction:\n{{ .Prompt }}\n### Response:\n'
SETTINGS = [("screen", "suite"), ("full164", os.path.join(HERE, "all164.json"))]


def modelfile_for(e, path):
    mode = e["modelfile"]
    if mode == "from-only":
        return f"FROM {path}\n"
    if mode == "metal-template":
        return f"FROM {path}\nTEMPLATE \"\"\"{METAL_TEMPLATE}\"\"\"\n"
    if mode == "donor":
        return R.donor_modelfile(path, e["donor"])
    raise ValueError(mode)


def generate(model, task_ids, options):
    """run_entries.generate plus the timing fields of the census harness."""
    gens, metrics = [], []
    for tid in task_ids:
        prompt = audit.TASKS[tid]["prompt"]
        t1 = time.monotonic()
        resp = audit.api("/api/chat", {
            "model": model,
            "messages": [{"role": "user", "content": f"{audit.INSTRUCTION}\n```python\n{prompt}\n```\n"}],
            "stream": False,
            "options": options,
            "keep_alive": "10m",
        })
        out = resp.get("message", {}).get("content", "")
        gens.append({"task_id": tid, "solution": out})
        m = audit.degeneration_features(prompt, out)
        m.update({"task_id": tid, "wall_s": round(time.monotonic() - t1, 2),
                  "eval_count": resp.get("eval_count"), "eval_duration_ns": resp.get("eval_duration"),
                  "prompt_eval_count": resp.get("prompt_eval_count"), "done_reason": resp.get("done_reason")})
        metrics.append(m)
    return gens, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    from evalplus.data import get_human_eval_plus
    audit.TASKS = get_human_eval_plus()
    entries = json.load(open(a.entries))
    if a.only:
        entries = [e for e in entries if e["id"] == a.only]
    os.makedirs(os.path.join(a.results_dir, "transcripts"), exist_ok=True)
    out_path = os.path.join(a.results_dir, "runs.jsonl")
    done = set()
    if os.path.exists(out_path):
        for l in open(out_path):
            if l.strip():
                r = json.loads(l)
                if not r.get("error"):
                    done.add((r["id"], r["setting"]))

    for i, e in enumerate(entries, 1):
        todo = [(s, t) for s, t in SETTINGS if (e["id"], s) not in done]
        if not todo:
            print(f"[{i}/{len(entries)}] skip {e['id']}", flush=True)
            continue
        path = e["path"]
        name = "p2tpl-" + e["id"].lower()
        mf = modelfile_for(e, path)
        mf_path = os.path.join("/root", f"Modelfile.{name}")
        with open(mf_path, "w") as f:
            f.write(mf)
        info = {"gguf_path": path, "modelfile_mode": e["modelfile"], "modelfile": mf,
                "modelfile_sha256": hashlib.sha256(mf.encode()).hexdigest(), "donor": e.get("donor")}
        try:
            info["file_sha256"] = hashlib.sha256(open(path, "rb").read()).hexdigest()
            try:
                info["hash"] = R.gguf_hash.describe(e["id"], path)
            except Exception as ex:
                info["hash_error"] = f"{type(ex).__name__}: {ex}"[:200]
            if R.sh(R.OLL, "show", "--modelfile", name).returncode != 0:
                c = R.sh(R.OLL, "create", name, "-f", mf_path)
                if c.returncode != 0:
                    raise RuntimeError("create failed: " + c.stderr.strip()[-200:])
            # what Ollama adopted: the template, and the blob it serves
            info["adopted_template"] = R.sh(R.OLL, "show", "--template", name).stdout
            info["adopted_modelfile"] = R.sh(R.OLL, "show", "--modelfile", name).stdout
            info["blob"] = R.model_blob(name)
            for setting, tasks in todo:
                task_ids = audit.SUITE if tasks == "suite" else json.load(open(tasks))
                rec = dict(e)
                rec.update({"setting": setting, "options": dict(R.BASELINE), "n_tasks": len(task_ids),
                            "tasks": tasks if tasks == "suite" else os.path.basename(tasks), "ts_start": time.time()})
                rec.update(info)
                try:
                    gens, metrics = generate(name, task_ids, R.BASELINE)
                    tpath = os.path.join(a.results_dir, "transcripts", f"{e['id']}__{setting}.jsonl")
                    with open(tpath, "w") as f:
                        for g in gens:
                            f.write(json.dumps(g) + "\n")
                    rec["transcript"] = os.path.basename(tpath)
                    rec["metrics"] = metrics
                    rec["trunc_frac"] = round(sum(m["done_reason"] == "length" for m in metrics) / len(metrics), 3)
                except Exception as ex:
                    rec["error"] = f"{type(ex).__name__}: {ex}"[:300]
                rec["ts_end"] = time.time()
                with open(out_path, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                status = "ERR " + rec["error"][:80] if rec.get("error") else f"{(rec['ts_end'] - rec['ts_start']) / 60:.1f} min, trunc {rec.get('trunc_frac')}"
                print(f"[{i}/{len(entries)}] {e['id']} ({setting}): {status}", flush=True)
        except Exception as ex:
            with open(out_path, "a") as f:
                f.write(json.dumps({"id": e["id"], "setting": "prepare", "error": f"{type(ex).__name__}: {ex}"[:300]}) + "\n")
            print(f"[{i}/{len(entries)}] {e['id']}: ERR {ex}", flush=True)
        finally:
            R.sh(R.OLL, "stop", name, timeout=120)
            R.sh(R.OLL, "rm", name, timeout=600)
            R.prune_orphan_blobs()
    print("TEMPLATE_TEST_DONE")


if __name__ == "__main__":
    main()
