#!/usr/bin/env python3
"""Screen one Ollama tag and write an in-toto eval-result record for it.

Order of work, so the record describes this run and nothing later:
  1. (optional) pull the tag
  2. write run_record.json: manifest, model and chat-template digests (checked against the
     blobs and against what the running server lists), runtime, decode settings, and the
     HumanEval+ data version with a digest of the 15 suite tasks
  3. self-test the scorer: the 15 reference solutions must all pass, otherwise stop
  4. generate the 15 screen answers with harness/audit.py (unchanged census harness)
  5. check that the tag and the served template did not change during generation
  6. score with the corrected scorer used for the paper (rerun-2026-10/scripts/score_runs.py)
  7. write generations.jsonl, scored.json and statement.json, and check the statement

On macOS, EvalPlus cannot set its memory limit and every test then fails silently, so the
script sets EVALPLUS_MAX_MEMORY_BYTES=-1 there unless you set it yourself; the run record
notes the value. The scorer self-test catches this and any other broken scoring setup.

Run it with the Python that has EvalPlus 0.3.1 installed (see the README quick start), with
the Ollama server running on this machine:
  .venv/bin/python harness/screen_intoto.py --tag qwen2.5-coder:3b-instruct-q3_K_M \\
      --out-dir my-record --evaluator-id https://github.com/YOUR-NAME
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "rerun-2026-10", "scripts"))

import intoto  # noqa: E402


suite_tasks_digest = intoto.suite_tasks_digest


def scorer_self_test(score, tasks, suite, work):
    """Score the suite's reference solutions; return how many pass (all must)."""
    os.makedirs(work, exist_ok=True)
    path = os.path.join(work, "reference_solutions.jsonl")
    with open(path, "w") as f:
        for t in suite:
            f.write(json.dumps({"task_id": t, "solution": tasks[t]["prompt"] + tasks[t]["canonical_solution"]}) + "\n")
    result = score(path, tasks)
    return sum(1 for v in (result or {}).values() if v is True)


def write_json(path, obj, **kw):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, **kw)
        f.write("\n")


class ScreenError(Exception):
    """A screen that must stop without writing a statement."""


def run_screen(tag, out_dir, evaluator_id, host, models_dir, backend, base_url, audit, score, tasks,
               evalplus_version, extra):
    """Record, generate, re-check, score and write the statement. Returns 1 if the check finds problems."""
    out = os.path.abspath(out_dir)
    if os.path.exists(os.path.join(out, "statement.json")):
        raise ScreenError(f"{out} already holds a statement; use a new --out-dir")
    os.makedirs(out, exist_ok=True)

    # 2. run record, before any generation
    try:
        rec = intoto.record_run(tag, host, models_dir, backend, evalplus_version, extra=extra)
    except (ValueError, FileNotFoundError, OSError) as e:
        raise ScreenError(f"cannot record the run: {e}")
    if rec["template_sha256"] and not rec["template_matches_runtime"]:
        raise ScreenError("the server serves a different chat template than the tag's template layer; "
                          "a record would not describe what was run, so nothing was generated")
    rr_path = os.path.join(out, "run_record.json")
    write_json(rr_path, rec)
    served_path = None
    if not rec["template_sha256"]:   # no template layer: keep the text the server served, as evidence
        text = intoto.ollama_api(host, "/api/show", {"model": tag}).get("template", "")
        served_path = os.path.join(out, "served_template.txt")
        with open(served_path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if intoto.sha256_file(served_path) != rec["template_served_by_runtime_sha256"]:
            raise ScreenError("the served template changed while it was being recorded")
    tpl = rec["template_sha256"] or rec["template_served_by_runtime_sha256"]
    print(f"run record: model {rec['model_sha256'][:12]}, template {tpl[:12]}"
          f"{'' if rec['template_sha256'] else ' (served; the tag has no template layer)'}", flush=True)

    work = os.path.join(out, "work")
    try:
        # 3. the scorer must pass the reference solutions before we trust it
        try:
            ok = scorer_self_test(score, tasks, audit.SUITE, os.path.join(work, "self_test"))
        except subprocess.TimeoutExpired:
            raise ScreenError("scorer self-test timed out")
        if ok != len(audit.SUITE):
            raise ScreenError(f"scorer self-test failed: {ok} of {len(audit.SUITE)} reference solutions passed, "
                              "so the scoring setup is broken (on macOS, check EVALPLUS_MAX_MEMORY_BYTES); "
                              "nothing was generated")
        print(f"scorer self-test: {ok} of {ok} reference solutions pass", flush=True)

        # 4. generation with the unchanged harness (no pull, keep the model)
        audit.TASKS = tasks
        audit.RESULTS = work
        result = audit.audit_one({"tag": tag, "no_pull": True}, audit.SUITE, keep=True)
        write_json(os.path.join(out, "audit_record.json"), result)
        if result.get("error") or not result.get("transcript"):
            raise ScreenError(f"generation failed: {result.get('error')}")
        gen_path = os.path.join(out, "generations.jsonl")
        shutil.copyfile(os.path.join(work, "transcripts", result["transcript"]), gen_path)

        # 5. nothing may have changed during generation
        try:
            changed = intoto.changes_since(rec, host, models_dir)
        except (ValueError, OSError) as e:
            raise ScreenError(f"could not re-check the tag after generation: {e}")
        if changed:
            raise ScreenError("not writing a statement: " + "; ".join(changed) + " during the run")

        # 6. scoring with the paper's corrected scorer
        try:
            per_task = score(gen_path, tasks)
        except subprocess.TimeoutExpired:
            raise ScreenError("scoring timed out")
        if per_task is None:
            raise ScreenError("scoring failed (EvalPlus produced no results)")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    n_pass = sum(1 for v in per_task.values() if v is True)
    scored = {"tag": tag, "suite": intoto.SUITE_FILE, "n_tasks": len(per_task), "n_pass": n_pass,
              "threshold": intoto.SCREEN_THRESHOLD, "passed": n_pass >= intoto.SCREEN_THRESHOLD,
              "trunc_frac": result.get("trunc_frac"), "per_task": per_task,
              "scorer_self_test": f"{ok} of {len(audit.SUITE)} reference solutions passed"}
    sc_path = os.path.join(out, "scored.json")
    write_json(sc_path, scored, sort_keys=True)

    # 7. statement
    st = intoto.build_statement(rec, rr_path, gen_path, sc_path, evaluator_id, base_url=base_url,
                                served_template_path=served_path)
    st_path = os.path.join(out, "statement.json")
    with open(st_path, "w") as f:
        f.write(intoto.dumps(st))
    problems = intoto.check_statement(st)
    verdict = "passes" if scored["passed"] else "is flagged by"
    print(f"{tag} solved {n_pass} of {len(per_task)}: it {verdict} the screen (threshold {intoto.SCREEN_THRESHOLD})")
    print(f"statement: {st_path}")
    for prob in problems:
        print("PROBLEM:", prob)
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Screen one Ollama tag and write an in-toto eval-result record.")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--evaluator-id", required=True, help="URI of whoever runs the screen, e.g. a GitHub profile")
    ap.add_argument("--host", help="Ollama server on this machine (default: $OLLAMA_HOST or 127.0.0.1:11434)")
    ap.add_argument("--models-dir", help="the server's model store (default: $OLLAMA_MODELS or ~/.ollama/models)")
    ap.add_argument("--backend", help="inference backend to record, for example Metal or CUDA")
    ap.add_argument("--pull", action="store_true", help="pull the tag before recording")
    ap.add_argument("--base-url", help="where the evidence files will be published (adds download links)")
    a = ap.parse_args(argv)

    bin_dir = os.path.dirname(sys.executable)
    if not os.path.exists(os.path.join(bin_dir, "evalplus.evaluate")):
        sys.exit(f"evalplus.evaluate not found next to {sys.executable}; run this with the Python "
                 "that has evalplus==0.3.1 installed (see the README quick start)")
    import evalplus
    from evalplus.data import get_human_eval_plus
    if evalplus.__version__ != "0.3.1":
        print(f"warning: EvalPlus {evalplus.__version__}; the paper used 0.3.1", file=sys.stderr)

    if sys.platform == "darwin" and "EVALPLUS_MAX_MEMORY_BYTES" not in os.environ:
        os.environ["EVALPLUS_MAX_MEMORY_BYTES"] = "-1"   # macOS cannot set the limit; tests would all fail
    host = intoto.normalize_host(a.host)
    os.environ["OLLAMA_HOST"] = host
    import audit                      # census harness, imported unchanged
    from score_runs import score      # corrected scorer used for the paper's numbers
    audit.OLLAMA = host
    if not shutil.which(audit.OLLAMA_BIN):
        sys.exit(f"the ollama command ({audit.OLLAMA_BIN}) is not on PATH; set OLLAMA_BIN to its full path")

    if os.path.exists(os.path.join(os.path.abspath(a.out_dir), "statement.json")):
        sys.exit(f"{a.out_dir} already holds a statement; use a new --out-dir")
    if a.pull:
        try:
            p = subprocess.run([audit.OLLAMA_BIN, "pull", a.tag], capture_output=True, text=True, timeout=7200)
        except subprocess.TimeoutExpired:
            sys.exit("pull timed out after two hours")
        if p.returncode != 0:
            sys.exit(f"pull failed: {p.stderr.strip()[-300:]}")
    tasks = get_human_eval_plus()
    extra = intoto.evalplus_info(tasks, audit.SUITE)
    try:
        return run_screen(a.tag, a.out_dir, a.evaluator_id, host, a.models_dir, a.backend, a.base_url,
                          audit, score, tasks, evalplus.__version__, extra)
    except ScreenError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    sys.exit(main())
