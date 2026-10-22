#!/usr/bin/env python3
"""Serial EvalPlus re-scoring of every transcript set the paper reports.

Why. The EvalPlus scorer is load-sensitive: HumanEval/15 (string_sequence, plus inputs with n up to
about 10^6) can exceed its per-test time limit when scoring runs in a parallel pool. This script
re-evaluates generations ONE AT A TIME (one evaluation in flight, default EvalPlus time limits), so the
only thing that changes against the original scorers is the load.

What is identical to the original scorers
  * Transcripts are read the same way (task_id -> solution, a later line wins).
  * Each transcript is padded to the full 164-task HumanEval+ sample file with the placeholder the
    original scorer used, and that file is passed through the `evalplus.sanitize` CLI, exactly as
    harness/score_smoke.py, harness/fullrun.py, analysis/score_experiments.py and
    rerun-2026-10/scripts/score_runs.py (used by rescore_census.py) do. The sanitized solution of each
    attempted task is what gets evaluated.
  * Each (run, task) instance is evaluated with evalplus.evaluate.check_correctness, the function
    `evalplus.evaluate` submits to its worker pool, with the arguments it uses there (base and plus
    inputs, fast_check=True, DEFAULT_MIN_TIME_LIMIT, DEFAULT_GT_TIME_LIMIT_FACTOR) and the ground
    truth from evalplus.evaluate.get_groundtruth (the local EvalPlus cache). A task passes only when
    base_status and plus_status are both "pass".
  * Paper-1 tuning configurations (A1 / screen-tuning numbers) are re-evaluated from the exact
    sanitized solution stored in their *_eval_results.json.
What differs: no ProcessPoolExecutor; instances are evaluated sequentially in this process (each
check still runs the generated code in its own child process, as EvalPlus does).

Selection. For every set the existing per-task verdicts are taken as they are. Every instance that is
a failure in any existing scoring of it is re-evaluated; passes stay passes, except a seeded random 3%
sample of passes per set (random.Random(SEED), sorted instance list, ceil(3%)) that is re-evaluated to
confirm none flips to fail. Sets whose original scorer stored only counts (no per-task verdicts) are
re-evaluated in full. Each flip is diagnosed in a further child process (same guard and limits) that
times every test and records the first exception.

Usage (python3 -E keeps the user site-packages where EvalPlus 0.3.1 is installed):
  python3 -E serial_rescore.py list                 # sets, runs, instances to evaluate
  python3 -E serial_rescore.py run [SET ...]        # evaluate serially (resumable checkpoint)
  python3 -E serial_rescore.py report               # write <set>_serial.jsonl, flips.jsonl, SERIAL_REPORT.md

Environment (all optional; defaults follow the project layout relative to this file):
  P2_ROOT             paper-2 project root (default: three levels above this file)
  RERUN_RESULTS       rerun-2026-10/pod-results directory
  CENSUS_TRANSCRIPTS  census transcripts (results/pod_archive/results/transcripts; byte-identical to
                      results/audit_data_full.tgz:results/transcripts)
  P1_RESULTS          paper-1 results directory (tuning configurations)
  EVALPLUS_BIN        directory holding evalplus.sanitize (default ~/Library/Python/3.9/bin)
  SERIAL_OUT          output directory (default: this file's directory)
  SERIAL_WORK         work directory for sanitized samples and the checkpoint
"""
import glob
import hashlib
import json
import math
import multiprocessing
import os
import platform
import random
import subprocess
import sys
import time
from collections import Counter, OrderedDict, defaultdict


def _p(name, default):
    return os.path.abspath(os.path.expanduser(os.environ.get(name, default)))


HERE = os.path.dirname(os.path.abspath(__file__))
P2 = _p("P2_ROOT", os.path.join(HERE, "..", "..", ".."))
RERUN = _p("RERUN_RESULTS", os.path.join(P2, "..", "p2-v2-work", "rerun-2026-10", "pod-results"))
CENSUS_T = _p("CENSUS_TRANSCRIPTS", os.path.join(P2, "results", "pod_archive", "results", "transcripts"))
P1_RES = _p("P1_RESULTS", os.path.join(P2, "p1-results-not-released"))  # set QUANTCHECK_P1_RESULTS
EVALPLUS_BIN = _p("EVALPLUS_BIN", "~/Library/Python/3.9/bin")
OUT = _p("SERIAL_OUT", HERE)
WORK = _p("SERIAL_WORK", os.path.join(OUT, "_work"))
CKPT = os.path.join(WORK, "instances.jsonl")

SEED = 20261021
SAMPLE_FRAC = 0.03
PH_RUNS = "pass  # placeholder-unattempted"   # score_smoke.py, score_runs.py (rescore_census.py)
PH_PLAIN = "pass"                             # fullrun.py, score_experiments.py

SET_ORDER = ["census_smoke", "census_full164", "rerun_results", "rerun_r2", "rerun_r3", "rerun_r3b",
             "rerun_r5", "rerun_r6", "rerun_p0", "rerun_p0c", "rerun_g1", "mac", "metalrep", "native",
             "sensitivity", "tuning_p1_humaneval", "tuning_p1_mbpp"]


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def rel(path):
    try:
        return os.path.relpath(path, os.path.dirname(P2))
    except ValueError:
        return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ set definitions
def _universe_tasks(name):
    if name == "smoke15":
        return sorted(json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"])
    if name == "heldout49":
        return sorted(json.load(open(os.path.join(P2, "heldout_49.json"))))
    raise KeyError(name)


def _run(set_name, key, transcript, universe, tasks, old, old_n, old_source, placeholder, **extra):
    """old: {task_id: bool} existing per-task verdicts (None = only a count was stored).
    old_alt: other existing per-task scorings of the same instances (failures there are re-evaluated)."""
    r = {"set": set_name, "key": key, "transcript": transcript, "universe": universe, "tasks": tasks,
         "old": old, "old_n_pass": old_n, "old_source": old_source, "placeholder": placeholder,
         "dataset": "humaneval"}
    r.update(extra)
    return r


def census_smoke():
    rs = jl(os.path.join(RERUN, "census_rescore.jsonl"))
    sc = {r["tag"]: r for r in jl(os.path.join(P2, "results", "audit_scored.jsonl"))}
    suite = _universe_tasks("smoke15")
    out = []
    for r in rs:
        o = sc[r["tag"]]
        assert sorted(r["per_task"]) == suite, r["tag"]
        out.append(_run("census_smoke", r["tag"], os.path.join(CENSUS_T, r["transcript"]), "smoke15", suite,
                        r["per_task"], r["n_pass"], "census_rescore.jsonl (pod, 6-worker pool)", PH_RUNS,
                        tag=r["tag"], channel=o.get("channel"),
                        old_alt={"audit_scored.jsonl (census, Aug 2026)": o["per_task"]},
                        old_n_pass_census_original=o["smoke_pass"]))
    return out


def census_full164():
    out = []
    for r in jl(os.path.join(P2, "results", "fullrun_scores.jsonl")):
        safe = r["tag"].replace(":", "_").replace("/", "_") + ".full164.jsonl"
        out.append(_run("census_full164", r["tag"], os.path.join(CENSUS_T, safe), "full164", None, None,
                        r["full_pass"], "results/fullrun_scores.jsonl (count only; per-task not stored)",
                        PH_PLAIN, tag=r["tag"]))
    return out


def _setting_universe(setting):
    if setting == "heldout49":
        return "heldout49"
    if setting == "full164":
        return "full164"
    return "smoke15"


def rerun(dirname):
    def build():
        d = os.path.join(RERUN, dirname)
        runs = {(r["id"], r["setting"]): r for r in jl(os.path.join(d, "runs.jsonl"))}
        latest = OrderedDict()
        dups = Counter()
        for r in jl(os.path.join(d, "scored.jsonl")):       # last record per key, as numbers_v3.latest
            k = (r["id"], r["setting"])
            if k in latest:
                dups[k] += 1
                assert latest[k]["per_task"] == r["per_task"], f"conflicting duplicate {k}"
            latest[k] = r
        out = []
        for (i, s), r in latest.items():
            run = runs[(i, s)]
            out.append(_run("rerun_" + (dirname.split("results-")[-1] if "-" in dirname else "results"),
                            f"{i}|{s}", os.path.join(d, "transcripts", run["transcript"]),
                            _setting_universe(s), sorted(r["per_task"]), r["per_task"], r["n_pass"],
                            f"{dirname}/scored.jsonl (pod, score_runs.py pool)", PH_RUNS,
                            id=i, setting=s, tag=r.get("tag")))
        return out
    return build


def mac_like(dirname, set_name):
    def build():
        d = os.path.join(P2, dirname)
        ar = [a for a in jl(os.path.join(d, "audit_results.jsonl"))
              if a.get("transcript") and not a.get("error") and not a.get("skip")]
        sc = jl(os.path.join(d, "audit_scored.jsonl"))
        assert len(ar) == len(sc), (dirname, len(ar), len(sc))
        suite = _universe_tasks("smoke15")
        out = []
        for a, s in zip(ar, sc):     # score_smoke.py appends in audit_results order
            assert a["tag"] == s["tag"]
            key = a["tag"] if a["tag"] != "macnight" else a["transcript"].replace(".jsonl", "")
            out.append(_run(set_name, key, os.path.join(d, "transcripts", a["transcript"]), "smoke15", suite,
                            s["per_task"], s["smoke_pass"], f"{dirname}/audit_scored.jsonl (Mac, score_smoke.py)",
                            PH_RUNS, tag=a["tag"]))
        return out
    return build


def native():
    exp = {r["file"]: r for r in json.load(open(os.path.join(P2, "analysis", "experiments.json")))["native"]}
    out = []
    for tp in sorted(glob.glob(os.path.join(P2, "results-native", "transcripts", "*.jsonl"))):
        e = exp[os.path.basename(tp)]
        out.append(_run("native", os.path.basename(tp).replace(".jsonl", ""), tp, "full164", None, None,
                        e["full164"], "analysis/experiments.json (Mac, score_experiments.py; counts only)",
                        PH_PLAIN, old_n_pass_smoke15=e["smoke15"]))
    return out


def sensitivity():
    exp = {r["artifact"]: r for r in json.load(open(os.path.join(P2, "analysis", "experiments.json")))["sensitivity"]}
    held = _universe_tasks("heldout49")
    out = []
    for tp in sorted(glob.glob(os.path.join(P2, "results-sensitivity", "transcripts", "*.jsonl"))):
        name = os.path.basename(tp).replace(".jsonl", "")
        e = exp[name]
        out.append(_run("sensitivity", name, tp, "heldout49", held, None, e["passed"],
                        "analysis/experiments.json (Mac, score_experiments.py; counts only)", PH_PLAIN))
    return out


def tuning(kind):
    def build():
        out = []
        for f in sorted(glob.glob(os.path.join(P1_RES, f"*.{kind}.samples-sanitized_eval_results.json"))):
            cfg = os.path.basename(f).split(f".{kind}.")[0]
            ev = json.load(open(f))["eval"]
            old, reasons, sols = {}, {}, {}
            for t, v in ev.items():
                assert len(v) == 1, (f, t)
                e = v[0]
                old[t] = e["base_status"] == "pass" and e["plus_status"] == "pass"
                reasons[t] = {"base_status": e["base_status"], "plus_status": e["plus_status"],
                              "base_fail_tests_n": len(e.get("base_fail_tests") or []),
                              "plus_fail_tests_n": len(e.get("plus_fail_tests") or [])}
                sols[t] = e["solution"]
            out.append(_run("tuning_p1_" + kind, cfg, f, "full164" if kind == "humaneval" else "mbpp378",
                            sorted(old), old, sum(old.values()),
                            f"paper-1 {kind} eval_results (Mac, evalplus.evaluate default pool)", None,
                            dataset=kind, old_reasons=reasons, solutions=sols))
        return out
    return build


SETS = {
    "census_smoke": census_smoke, "census_full164": census_full164,
    "rerun_results": rerun("results"), "rerun_r2": rerun("results-r2"), "rerun_r3": rerun("results-r3"),
    "rerun_r3b": rerun("results-r3b"), "rerun_r5": rerun("results-r5"), "rerun_r6": rerun("results-r6"),
    "rerun_p0": rerun("results-p0"), "rerun_p0c": rerun("results-p0c"), "rerun_g1": rerun("results-g1"),
    "mac": mac_like("results-mac", "mac"), "metalrep": mac_like("results-metalrep", "metalrep"),
    "native": native, "sensitivity": sensitivity,
    "tuning_p1_humaneval": tuning("humaneval"), "tuning_p1_mbpp": tuning("mbpp"),
}


# ------------------------------------------------------------------ transcripts and sanitizing
def read_gens(path):
    gens = {}
    for l in open(path):
        if l.strip():
            g = json.loads(l)
            gens[g["task_id"]] = g["solution"]
    return gens


_HE_TASKS = None


def he_task_ids():
    global _HE_TASKS
    if _HE_TASKS is None:
        from evalplus.data import get_human_eval_plus
        _HE_TASKS = list(get_human_eval_plus().keys())
    return _HE_TASKS


def sanitized_solutions(run):
    """{task_id: sanitized solution} for the attempted tasks, via the evalplus.sanitize CLI on the
    164-task padded sample file, as the original scorers do."""
    if run["dataset"] != "humaneval" or run["placeholder"] is None:
        return run["solutions"], {"sanitizer": "stored solution (already sanitized by the original pipeline)"}
    gens = read_gens(run["transcript"])
    wd = os.path.join(WORK, run["set"], hashlib.sha1(run["key"].encode()).hexdigest()[:16])
    os.makedirs(wd, exist_ok=True)
    spath = os.path.join(wd, "samples.jsonl")
    san = spath.replace(".jsonl", "-sanitized.jsonl")
    if not os.path.exists(san):
        with open(spath, "w") as f:
            for tid in he_task_ids():
                f.write(json.dumps({"task_id": tid, "solution": gens.get(tid, run["placeholder"])}) + "\n")
        env = dict(os.environ, PATH=os.environ["PATH"] + ":" + EVALPLUS_BIN)
        subprocess.run([os.path.join(EVALPLUS_BIN, "evalplus.sanitize"), "--samples", spath],
                       capture_output=True, env=env)
    src = san if os.path.exists(san) else spath
    sol = {}
    for l in open(src):
        if l.strip():
            g = json.loads(l)
            sol[g["task_id"]] = g["solution"]
    meta = {"sanitizer": "evalplus.sanitize CLI" if src == san else "sanitize produced no file; raw used",
            "attempted": sorted(gens), "work_dir": wd}
    return {t: sol[t] for t in gens if t in sol}, meta


# ------------------------------------------------------------------ selection
def selection(set_name, runs):
    """[(run_key, task_id, kind)] in evaluation order; kind in fail | sample_pass | full."""
    todo, passes = [], []
    for r in runs:
        if r["old"] is None:
            continue
        for t in r["tasks"]:
            olds = [r["old"].get(t, False)] + [alt.get(t, False) for alt in (r.get("old_alt") or {}).values()]
            if not all(olds):
                todo.append((r["key"], t, "fail"))
            else:
                passes.append((r["key"], t))
    passes.sort()
    k = math.ceil(SAMPLE_FRAC * len(passes)) if passes else 0
    sample = set(random.Random(SEED).sample(passes, k)) if k else set()
    for r in runs:
        if r["old"] is None:
            continue
        for t in r["tasks"]:
            if (r["key"], t) in sample:
                todo.append((r["key"], t, "sample_pass"))
    return todo, len(passes), k


def full_tasks(run, sols):
    """For count-only sets: every task of the universe that the transcript attempted."""
    if run["universe"] == "full164":
        return [t for t in he_task_ids() if t in sols]
    return [t for t in run["tasks"] if t in sols]


# ------------------------------------------------------------------ evaluation
_DS = {}


def dataset(name):
    if name not in _DS:
        from evalplus.evaluate import get_groundtruth
        from evalplus.eval._special_oracle import MBPP_OUTPUT_NOT_NONE_TASKS
        if name == "humaneval":
            from evalplus.data import get_human_eval_plus, get_human_eval_plus_hash
            probs, h = get_human_eval_plus(), get_human_eval_plus_hash()
            exp = get_groundtruth(probs, h, [])
        else:
            from evalplus.data import get_mbpp_plus, get_mbpp_plus_hash
            probs, h = get_mbpp_plus(), get_mbpp_plus_hash()
            exp = get_groundtruth(probs, h, MBPP_OUTPUT_NOT_NONE_TASKS)
        _DS[name] = (probs, exp, h)
    return _DS[name]


def _reason(stat, details, n):
    if stat == "pass":
        return "pass"
    done = len(details)
    if stat == "timeout":
        return f"timeout: process killed at the task time budget after {done} of {n} tests"
    if done == 0:
        return "fail before the first test (code did not exec, or entry point missing)"
    if not details[-1]:
        return f"fail at test {done - 1} of {n} (wrong output, exception, or per-test time limit)"
    return f"fail: only {done} of {n} tests completed"


def evaluate_one(ds, task_id, solution):
    from evalplus.config import DEFAULT_GT_TIME_LIMIT_FACTOR, DEFAULT_MIN_TIME_LIMIT
    from evalplus.evaluate import check_correctness
    probs, exp, _ = dataset(ds)
    p = probs[task_id]
    t0 = time.time()
    res = check_correctness(ds, 0, p, solution, exp[task_id], False, True, task_id,
                            DEFAULT_MIN_TIME_LIMIT, DEFAULT_GT_TIME_LIMIT_FACTOR)
    wall = time.time() - t0
    bs, bd = res["base"]
    ps, pd = res["plus"]
    return {"base_status": bs, "plus_status": ps, "pass": bs == "pass" and ps == "pass",
            "base_reason": _reason(bs, list(bd), len(p["base_input"])),
            "plus_reason": _reason(ps, list(pd), len(p["plus_input"])), "wall_s": round(wall, 3)}


def _diag_child(entry_point, code, inputs, time_limits, elapsed, fail_idx, exc_buf, stage):
    """Mirror of evalplus.eval.unsafe_execute (same guard, tempdir and per-test time limits) that records
    the wall time of each test and the first exception raised by the generated code. Output equality is
    not checked here; EvalPlus' own verdict says which test failed."""
    from evalplus.eval import query_maximum_memory_bytes
    from evalplus.eval.utils import create_tempdir, reliability_guard, swallow_io, time_limit
    with create_tempdir():
        import shutil
        rmtree, rmdir, chdir = shutil.rmtree, os.rmdir, os.chdir
        reliability_guard(maximum_memory_bytes=query_maximum_memory_bytes())

        def put(msg):
            b = msg.encode("utf-8", "replace")[: len(exc_buf) - 1]
            exc_buf.value = b
        g = {}
        try:
            with swallow_io():
                exec(code, g)
                fn = g[entry_point]
        except BaseException as e:  # noqa: BLE001
            stage.value = 1
            put(f"load: {type(e).__name__}: {e}")
        else:
            stage.value = 2
            for i, inp in enumerate(inputs):
                t0 = time.perf_counter()
                try:
                    with time_limit(time_limits[i]):
                        with swallow_io():
                            fn(*inp)
                    elapsed[i] = time.perf_counter() - t0
                except BaseException as e:  # noqa: BLE001
                    elapsed[i] = time.perf_counter() - t0
                    fail_idx.value = i
                    put(f"test {i}: {type(e).__name__}: {e}")
                    break
            stage.value = 3
        shutil.rmtree, os.rmdir, os.chdir = rmtree, rmdir, chdir


def diagnose(ds, task_id, solution):
    from evalplus.config import DEFAULT_GT_TIME_LIMIT_FACTOR, DEFAULT_MIN_TIME_LIMIT
    probs, exp, _ = dataset(ds)
    p = probs[task_id]
    out = {}
    for part in ("base", "plus"):
        inputs = p[f"{part}_input"]
        ref = exp[task_id][f"{part}_time"]
        limits = [max(DEFAULT_MIN_TIME_LIMIT, DEFAULT_GT_TIME_LIMIT_FACTOR * t) for t in ref]
        timeout = min(60, sum(limits)) + 1
        elapsed = multiprocessing.Array("d", [-1.0] * len(inputs))
        fail_idx = multiprocessing.Value("i", -1)
        exc_buf = multiprocessing.Array("c", 400)
        stage = multiprocessing.Value("i", 0)
        pr = multiprocessing.Process(target=_diag_child, args=(p["entry_point"], solution, inputs, limits,
                                                                elapsed, fail_idx, exc_buf, stage))
        t0 = time.time()
        pr.start()
        pr.join(timeout=timeout + 1)
        if pr.is_alive():
            pr.terminate()
            time.sleep(0.1)
        if pr.is_alive():
            pr.kill()
        el = list(elapsed)
        ratios = [(el[i] / limits[i], i) for i in range(len(el)) if el[i] >= 0]
        worst = max(ratios) if ratios else (None, None)
        out[part] = {"n_tests": len(inputs), "tests_timed": len(ratios),
                     "first_exception": exc_buf.value.decode("utf-8", "replace") or None,
                     "fail_index": fail_idx.value if fail_idx.value >= 0 else None,
                     "max_runtime_over_limit": round(worst[0], 4) if worst[0] is not None else None,
                     "max_ratio_test": worst[1], "limit_of_that_test_s": round(limits[worst[1]], 3) if worst[1] is not None else None,
                     "sum_runtime_s": round(sum(e for e in el if e > 0), 3),
                     "process_budget_s": round(timeout, 2), "wall_s": round(time.time() - t0, 3),
                     "completed": stage.value == 3, "killed_at_budget": stage.value in (0, 2)}
    return out


# ------------------------------------------------------------------ checkpoint
def load_ckpt():
    done = {}
    if os.path.exists(CKPT):
        for r in jl(CKPT):
            done[(r["set"], r["key"], r["task_id"])] = r
    return done


def cmd_list(names):
    tot = 0
    for name in names:
        runs = SETS[name]()
        todo, npass, k = selection(name, runs)
        n_full = sum(1 for r in runs if r["old"] is None)
        print(f"{name:<22} runs={len(runs):<4} fails={sum(1 for x in todo if x[2] == 'fail'):<5} "
              f"passes={npass:<5} sample={k:<4} count-only runs={n_full}")
        tot += len(todo)
    print("selected (excl. count-only sets):", tot)


def cmd_run(names):
    os.makedirs(WORK, exist_ok=True)
    done = load_ckpt()
    log = open(os.path.join(WORK, "run_log.jsonl"), "a")
    with open(CKPT, "a") as ck:
        for name in names:
            runs = SETS[name]()
            by_key = {r["key"]: r for r in runs}
            todo, npass, k = selection(name, runs)
            plan = defaultdict(list)
            for key, t, kind in todo:
                plan[key].append((t, kind))
            t_set = time.time()
            ev_n = 0
            log.write(json.dumps({"set": name, "event": "start", "ts": t_set, "loadavg": os.getloadavg()}) + "\n")
            log.flush()
            print(f"== {name}: {len(runs)} runs", flush=True)
            for r in runs:
                t_s = time.time()
                sols, meta = sanitized_solutions(r)
                san_s = time.time() - t_s
                items = plan.get(r["key"], [])
                if r["old"] is None:
                    items = [(t, "full") for t in full_tasks(r, sols)]
                for t, kind in items:
                    if (name, r["key"], t) in done:
                        continue
                    if t not in sols:
                        rec = {"set": name, "key": r["key"], "task_id": t, "kind": kind, "pass": False,
                               "base_status": None, "plus_status": None, "unattempted": True}
                    else:
                        rec = {"set": name, "key": r["key"], "task_id": t, "kind": kind,
                               "loadavg1": round(os.getloadavg()[0], 2), "ts": round(time.time(), 1)}
                        rec.update(evaluate_one(r["dataset"], t, sols[t]))
                        ev_n += 1
                        old = r["old"].get(t) if r["old"] is not None else None
                        if old is not None and old != rec["pass"]:
                            rec["diag"] = diagnose(r["dataset"], t, sols[t])
                        elif r["old"] is None and t == "HumanEval/15":
                            rec["diag"] = diagnose(r["dataset"], t, sols[t])
                    rec["sanitize_s"] = round(san_s, 2)
                    ck.write(json.dumps(rec) + "\n")
                    ck.flush()
                    done[(name, r["key"], t)] = rec
                    if rec.get("diag") is not None and r["old"] is not None:
                        print(f"   FLIP {r['key']} {t}: old={'pass' if r['old'].get(t) else 'fail'} "
                              f"new={'pass' if rec['pass'] else 'fail'} ({rec['base_status']}/{rec['plus_status']})",
                              flush=True)
            el = time.time() - t_set
            log.write(json.dumps({"set": name, "event": "end", "ts": time.time(), "elapsed_s": round(el, 1),
                                  "evaluated_now": ev_n, "loadavg": os.getloadavg()}) + "\n")
            log.flush()
            print(f"== {name}: done, {ev_n} instances evaluated in {el:.0f}s", flush=True)


def flipped(done, name, runs_by_key):
    """[(run, task_id, checkpoint record)] whose serial verdict differs from the existing verdict."""
    out = []
    for (s, key, t), x in sorted(done.items()):
        if s != name or x.get("unattempted"):
            continue
        r = runs_by_key[key]
        if r["old"] is not None and bool(r["old"].get(t, False)) != bool(x["pass"]):
            out.append((r, t, x))
    return out


def cmd_stability(names, base_reps=2, near_reps=5, near=0.25):
    """Re-evaluate every flipped instance again, serially: base_reps more times, or near_reps more
    times when the flip's diagnosis put some test at >= `near` of its per-test time limit."""
    done = load_ckpt()
    path = os.path.join(WORK, "stability.jsonl")
    have = Counter()
    if os.path.exists(path):
        for r in jl(path):
            have[(r["set"], r["key"], r["task_id"])] += 1
    with open(path, "a") as f:
        for name in names:
            runs = {r["key"]: r for r in SETS[name]()}
            cache = {}
            fl = flipped(done, name, runs)
            t0 = time.time()
            for r, t, x in fl:
                ratio = max((x.get("diag") or {}).get(p, {}).get("max_runtime_over_limit") or 0 for p in ("base", "plus"))
                reps = near_reps if ratio >= near else base_reps
                if r["key"] not in cache:
                    cache[r["key"]] = sanitized_solutions(r)[0]
                for i in range(have[(name, r["key"], t)], reps):
                    rec = {"set": name, "key": r["key"], "task_id": t, "rep": i, "first_ratio": ratio,
                           "loadavg1": round(os.getloadavg()[0], 2), "ts": round(time.time(), 1)}
                    rec.update(evaluate_one(r["dataset"], t, cache[r["key"]][t]))
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
            if fl:
                print(f"== stability {name}: {len(fl)} flips re-checked in {time.time() - t0:.0f}s", flush=True)


# ------------------------------------------------------------------ report
def _load_analyze():
    import importlib.util
    spec = importlib.util.spec_from_file_location("analyze", os.path.join(P2, "analysis", "analyze.py"))
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    return A


def _classify(A, rows, score):
    """Transcribed from paper-v3/analysis/numbers_v3.py classify(): group baseline = median of the
    high-precision tags (analyze.HIGH) of the same analyze.size_key group."""
    import statistics
    fam = defaultdict(list)
    for r in rows:
        fam[A.size_key(r["tag"])].append(r)
    base = {}
    for k, g in fam.items():
        hi = [score(x) for x in g if any(h in x["tag"] for h in A.HIGH)]
        base[k] = statistics.median(hi) if hi else None
    cls = {}
    for r in rows:
        b = base[A.size_key(r["tag"])]
        s = score(r)
        if b is None:
            cls[r["tag"]] = "NO_BASELINE"
        elif (s / b if b else 0) >= 0.6:
            cls[r["tag"]] = "HEALTHY"
        elif s <= 2 and b >= 8:
            cls[r["tag"]] = "SUSPECT"
        elif b < 8:
            cls[r["tag"]] = "COLLAPSED"
        else:
            cls[r["tag"]] = "DEGRADED"
    return cls


def census_impact(smoke_recs, full_recs):
    """Screen-level consequences of the serial census scores (same rules as numbers_v3.py)."""
    A = _load_analyze()
    sc = {r["tag"]: r for r in jl(os.path.join(P2, "results", "audit_scored.jsonl"))}
    rs = {r["tag"]: r for r in jl(os.path.join(RERUN, "census_rescore.jsonl"))}
    ser = {r["tag"]: r for r in smoke_recs}
    official = [sc[t] for t in sc if sc[t].get("channel") == "ollama-official"]
    community = [sc[t] for t in sc if sc[t].get("channel") == "hf-community"]
    scores = {"original (audit_scored)": lambda r: r["smoke_pass"],
              "pod rescore (census_rescore)": lambda r: rs[r["tag"]]["n_pass"],
              "serial": lambda r: ser[r["tag"]]["n_pass"]}
    out = {}
    for name, fn in scores.items():
        cls = _classify(A, official, fn)
        out[name] = {"classes": dict(sorted(Counter(cls.values()).items())),
                     "stage1_flags_lt9": sum(1 for r in official if fn(r) < 9),
                     "suspects": sorted(t for t, c in cls.items() if c == "SUSPECT"),
                     "community_ge9": sum(1 for r in community if fn(r) >= 9)}
    out["he15_pass_official"] = {"original": sum(bool(r["per_task"].get("HumanEval/15")) for r in official),
                                 "pod rescore": sum(bool(rs[r["tag"]]["per_task"].get("HumanEval/15")) for r in official),
                                 "serial": sum(bool(ser[r["tag"]]["per_task"].get("HumanEval/15")) for r in official)}
    out["official_changed_vs_rescore"] = sum(1 for r in official if ser[r["tag"]]["n_pass"] != rs[r["tag"]]["n_pass"])
    out["official_changed_vs_original"] = sum(1 for r in official if ser[r["tag"]]["n_pass"] != r["smoke_pass"])
    out["full164"] = {r["tag"]: {"old": r["old_n_pass"], "serial": r["n_pass"],
                                 "he15_serial": r["per_task"].get("HumanEval/15")} for r in full_recs}
    return out


def _env():
    import evalplus
    from evalplus.data.humaneval import HUMANEVAL_PLUS_VERSION
    from evalplus.data.mbpp import MBPP_PLUS_VERSION
    from evalplus.data.utils import CACHE_DIR
    from evalplus.data import get_human_eval_plus_hash, get_mbpp_plus_hash
    he_h, mb_h = get_human_eval_plus_hash(), get_mbpp_plus_hash()
    pk = {}
    for h in (he_h, mb_h):
        f = os.path.join(CACHE_DIR, f"{h}.pkl")
        if os.path.exists(f):
            pk[os.path.basename(f)] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
    vers = {}
    for m in ("tree_sitter", "tree_sitter_python", "numpy", "psutil"):
        try:
            from importlib.metadata import version
            vers[m] = version(m.replace("_", "-"))
        except Exception:  # noqa: BLE001
            vers[m] = "?"
    return {"evalplus": evalplus.__version__, "humaneval_plus": HUMANEVAL_PLUS_VERSION, "humaneval_hash": he_h,
            "mbpp_plus": MBPP_PLUS_VERSION, "mbpp_hash": mb_h, "groundtruth_cache_mtime": pk,
            "python": platform.python_version(), "platform": platform.platform(),
            "cpu_count": multiprocessing.cpu_count(), "start_method": multiprocessing.get_start_method(),
            "packages": vers}


def cmd_report(names):
    done = load_ckpt()
    logs = jl(os.path.join(WORK, "run_log.jsonl")) if os.path.exists(os.path.join(WORK, "run_log.jsonl")) else []
    all_flips, summary = [], []
    for name in names:
        runs = SETS[name]()
        todo, npass, k = selection(name, runs)
        sel = {(key, t): kind for key, t, kind in todo}
        recs_out, missing = [], []
        s = {"set": name, "runs": len(runs), "evaluated": 0, "fail_reeval": 0, "sample_pass": 0,
             "full": 0, "pass_pool": npass, "sample_k": k, "fail_to_pass": Counter(), "pass_to_fail": Counter(),
             "old_total": 0, "new_total": 0, "unattempted": 0, "count_only": 0, "count_changes": [],
             "missing_transcripts": [], "incomplete": 0, "still_fail_status": []}
        for r in runs:
            if not os.path.exists(r["transcript"]):
                s["missing_transcripts"].append(rel(r["transcript"]))
                continue
            if r["old"] is None:
                s["count_only"] += 1
                tasks = r["tasks"] or he_task_ids()
                per = {}
                for t in tasks:
                    x = done.get((name, r["key"], t))
                    if x is None:
                        gens = read_gens(r["transcript"])
                        if t in gens:
                            s["incomplete"] += 1
                        per[t] = False
                        if t not in gens:
                            s["unattempted"] += 1
                        continue
                    per[t] = bool(x["pass"])
                    if not x["pass"] and not x.get("unattempted"):
                        s["still_fail_status"].append(f"{x['base_status']}/{x['plus_status']}")
                    s["evaluated"] += 0 if x.get("unattempted") else 1
                    s["full"] += 0 if x.get("unattempted") else 1
                n_new = sum(per.values())
                if n_new != r["old_n_pass"]:
                    s["count_changes"].append({"key": r["key"], "old": r["old_n_pass"], "new": n_new})
                flips_here = []
            else:
                per, flips_here = {}, []
                for t in r["tasks"]:
                    old = bool(r["old"].get(t, False))
                    x = done.get((name, r["key"], t))
                    kind = sel.get((r["key"], t))
                    if kind is None:
                        per[t] = old
                        continue
                    if x is None:
                        s["incomplete"] += 1
                        per[t] = old
                        continue
                    s["evaluated"] += 1
                    s["fail_reeval" if kind == "fail" else "sample_pass"] += 1
                    per[t] = bool(x["pass"])
                    if not per[t] and not old:
                        s["still_fail_status"].append(f"{x['base_status']}/{x['plus_status']}")
                    if per[t] != old:
                        f = {"set": name, "key": r["key"], "id": r.get("id", r["key"]), "tag": r.get("tag"),
                             "setting": r.get("setting"), "universe": r["universe"], "task_id": t,
                             "old_status": "pass" if old else "fail", "new_status": "pass" if per[t] else "fail",
                             "selected_as": kind, "old_source": r["old_source"],
                             "old_reason": (r.get("old_reasons") or {}).get(t,
                                            "not stored by the original scorer (only the per-task boolean)"),
                             "new_base_status": x["base_status"], "new_plus_status": x["plus_status"],
                             "new_base_reason": x.get("base_reason"), "new_plus_reason": x.get("plus_reason"),
                             "serial_wall_s": x.get("wall_s"), "loadavg1": x.get("loadavg1"),
                             "diagnosis": x.get("diag")}
                        alt = {src: bool(v.get(t, False)) for src, v in (r.get("old_alt") or {}).items()}
                        if alt:
                            f["other_old_scorings"] = alt
                        flips_here.append(f)
                        (s["fail_to_pass"] if per[t] else s["pass_to_fail"])[t] += 1
                n_new = sum(per.values())
            s["old_total"] += r["old_n_pass"]
            s["new_total"] += n_new
            rec = {"id": r.get("id", r["key"]), "tag": r.get("tag", r["key"]), "setting": r.get("setting"),
                   "channel": r.get("channel"), "universe": r["universe"], "transcript": rel(r["transcript"]),
                   "per_task": per, "n_pass": n_new, "n": len(per), "old_n_pass": r["old_n_pass"],
                   "old_source": r["old_source"],
                   "reevaluated": sorted(t for t in per if (name, r["key"], t) in done),
                   "flips": [{"task_id": f["task_id"], "old": f["old_status"], "new": f["new_status"]}
                             for f in flips_here]}
            for extra in ("old_n_pass_census_original", "old_n_pass_smoke15"):
                if extra in r:
                    rec[extra] = r[extra]
            if r.get("old_n_pass_smoke15") is not None:
                suite = _universe_tasks("smoke15")
                rec["n_pass_smoke15"] = sum(per.get(t, False) for t in suite)
            rec = {k2: v for k2, v in rec.items() if v is not None}
            recs_out.append(rec)
            all_flips.extend(flips_here)
        with open(os.path.join(OUT, f"{name}_serial.jsonl"), "w") as f:
            for rec in recs_out:
                f.write(json.dumps(rec) + "\n")
        st = [x for x in logs if x["set"] == name and x["event"] == "end"]
        s["wall_s"] = round(sum(x["elapsed_s"] for x in st), 1)
        s["records"] = recs_out
        summary.append(s)
    stab = defaultdict(list)
    sp = os.path.join(WORK, "stability.jsonl")
    if os.path.exists(sp):
        for x in jl(sp):
            stab[(x["set"], x["key"], x["task_id"])].append(x)
    for f in all_flips:
        reps = stab.get((f["set"], f["key"], f["task_id"]), [])
        f["serial_repeats"] = {"n": len(reps), "pass": sum(bool(x["pass"]) for x in reps),
                               "statuses": sorted(Counter(f"{x['base_status']}/{x['plus_status']}" for x in reps).items())}
    with open(os.path.join(OUT, "flips.jsonl"), "w") as f:
        for x in all_flips:
            f.write(json.dumps(x) + "\n")
    by = {s["set"]: s for s in summary}
    impact = None
    if "census_smoke" in by and "census_full164" in by:
        impact = census_impact(by["census_smoke"]["records"], by["census_full164"]["records"])
    if WORK != OUT:      # keep the provenance next to the outputs
        import shutil
        for fn in ("instances.jsonl", "run_log.jsonl", "stability.jsonl"):
            if os.path.exists(os.path.join(WORK, fn)):
                shutil.copy(os.path.join(WORK, fn), os.path.join(OUT, fn))
    json.dump({"env": _env(), "census_impact": impact,
               "sets": [{k2: (dict(v) if isinstance(v, Counter) else v) for k2, v in s.items()
                         if k2 != "records"} for s in summary]},
              open(os.path.join(OUT, "serial_summary.json"), "w"), indent=1)
    write_report(summary, all_flips, logs, impact)


NOTES = """## Notes and limits

- Only the load changes for the sets first scored on this Mac (results-mac, results-metalrep,
  results-native, results-sensitivity, paper-1 tuning configurations): same machine, same EvalPlus
  install and ground-truth cache, same sanitizer, minus the pool. The census and rerun sets were first
  scored on the RunPod pod (Python 3.12.3, tree-sitter 0.26.0 / tree-sitter-python 0.25.0, numpy 2.5.2,
  Linux fork start method, the pod's own ground-truth timings). This Mac has Python 3.9.6, tree-sitter
  0.23.2 / tree-sitter-python 0.23.6, numpy 2.0.2 and the spawn start method. EvalPlus (0.3.1) and the
  datasets (HumanEval+ v0.1.10, MBPP+ v0.2.0) are the same. Evidence that the platform difference does
  not move verdicts: no sampled pass failed, every other re-evaluated failure stayed a failure, and all
  flips are failures turning into passes on five tasks with slow plus tests (by longest single plus
  test, HumanEval/130 and HumanEval/15 have the 3rd- and 5th-slowest of the 164 HumanEval+ ground
  truths). HumanEval/15 results already varied between pod scorings of the same transcripts (0 of 305
  official tags in the census, 134 in the pod rescore), and the MBPP flips occur on the same Mac install
  as their original scoring, so only the pool differs there.
- Per-instance statuses of the original scorings were not kept (the scorers wrote eval_results.json to
  a temporary directory and kept only the per-task boolean), so the old failure reason of a pod or
  census flip is unknown; the paper-1 eval_results do keep it (all their flips were plus-test failures).
- The flip diagnosis reruns the sanitized solution in a child process with EvalPlus' guard and limits
  and times each test; "max runtime / per-test limit" is the largest ratio over all tests. A value well
  below 1 means the serial pass has headroom; MBPP/160 (about 0.9) is close to its limit even serially.
- Census full 164-task runs, results-native and results-sensitivity stored only counts, so they were
  re-evaluated in full and compared at count level.
- Scope: every EvalPlus score the paper cites comes from one of the sets above, including the
  screen-tuning data from paper 1 (HumanEval+ and MBPP+). The perplexity, tensor-comparison,
  output-statistic and timing numbers are not EvalPlus scores and are not affected.
- Downstream files that still read the pool scores (paper-v3/analysis/numbers_v3.py, a1_rescored.py,
  figures) must be pointed at the `*_serial.jsonl` files before the paper can say it reports serial
  scores throughout; this script does not modify them.
"""


def _q(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return "n/a"
    return f"{vals[0]:.2f} / {vals[len(vals) // 2]:.2f} / {vals[-1]:.2f}"


def write_report(summary, flips, logs, impact=None):
    env = _env()
    L = []
    w = L.append
    w("# Serial re-scoring of every reported transcript set\n")
    w(f"Generated {time.strftime('%Y-%m-%d %H:%M %Z')} by `serial_rescore.py report`.\n")
    w("Every score in the `*_serial.jsonl` files comes from evaluating generations one at a time (no worker "
      "pool, no other evaluation running), with EvalPlus' default time limits. Existing per-task verdicts "
      "were taken as they were; every instance that failed in any existing scoring was re-evaluated "
      f"serially, and a seeded 3% sample of passes per set (random.Random({SEED}) over the sorted pass "
      "instances, ceil(3%)) was re-evaluated to check that no pass turns into a failure. Sets whose scorer "
      "stored only counts were re-evaluated in full. Sanitizing is the original scorers' own: each "
      "transcript is padded to 164 tasks with the scorer's placeholder and passed through the "
      "`evalplus.sanitize` CLI; paper-1 tuning configurations are re-evaluated from the exact sanitized "
      "solutions stored in their eval_results. Each instance is evaluated with "
      "`evalplus.evaluate.check_correctness`, the function `evalplus.evaluate` submits to its pool, with "
      "the same arguments.\n")
    w("## Environment\n")
    w(f"- EvalPlus {env['evalplus']}; HumanEval+ {env['humaneval_plus']} (md5 {env['humaneval_hash']}); "
      f"MBPP+ {env['mbpp_plus']} (md5 {env['mbpp_hash']})")
    w(f"- Ground-truth cache (EvalPlus default location, reused, file mtime): {env['groundtruth_cache_mtime']}")
    w(f"- Python {env['python']} on {env['platform']}, {env['cpu_count']} CPUs, multiprocessing start method "
      f"`{env['start_method']}`; packages {env['packages']}")
    w("- Time limits: per test max(DEFAULT_MIN_TIME_LIMIT = 1.0 s, DEFAULT_GT_TIME_LIMIT_FACTOR = 4.0 x "
      "ground-truth time); per check min(60, sum of limits) + 1 s (EvalPlus defaults, unchanged)")
    la = [x["loadavg"][0] for x in logs if "loadavg" in x]
    if la:
        w(f"- 1-minute load average at set boundaries: {min(la):.2f} to {max(la):.2f} on {env['cpu_count']} CPUs "
          "(the serial evaluation itself accounts for about 1)")
    t_all = sum(x["elapsed_s"] for x in logs if x.get("event") == "end")
    w(f"- Total wall time of the serial runs: {t_all / 3600:.2f} h\n")
    w("## Per set\n")
    w("| Set | Universe | Runs | Re-evaluated: failures / 3% pass sample (of passes) / full | Passes old -> serial | fail->pass | pass->fail | Wall time |")
    w("|---|---|---|---|---|---|---|---|")
    for s in summary:
        f2p = sum(s["fail_to_pass"].values())
        p2f = sum(s["pass_to_fail"].values())
        uni = ",".join(sorted({r["universe"] for r in s["records"]}))
        cnt = f" (count level: {len(s['count_changes'])} runs changed)" if s["count_only"] else ""
        w(f"| {s['set']} | {uni} | {s['runs']} | {s['fail_reeval']} / {s['sample_pass']} (of {s['pass_pool']}) / "
          f"{s['full']} | {s['old_total']} -> {s['new_total']}{cnt} | {f2p} | {p2f} | {s['wall_s'] / 60:.1f} min |")
    w("\nOld sources: " + "; ".join(sorted({f"{s['set']}: {s['records'][0]['old_source']}" for s in summary if s['records']})) + "\n")
    w("## Flips by task id\n")
    tot = Counter()
    for f in flips:
        tot[(f["task_id"], f["old_status"], f["new_status"])] += 1
    w("All sets: " + (", ".join(f"{t} {o}->{n}: {c}" for (t, o, n), c in sorted(tot.items(), key=lambda x: -x[1])) or "none") + "\n")
    w("| Set | Task | fail->pass | pass->fail | serial max runtime / per-test limit (min / median / max) | serial repeats all pass |")
    w("|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for f in flips:
        groups[(f["set"], f["task_id"])].append(f)
    for (sname, t), fl in sorted(groups.items()):
        ratios = [max((f.get("diagnosis") or {}).get(p, {}).get("max_runtime_over_limit") or 0 for p in ("base", "plus")) for f in fl]
        rep_ok = sum(1 for f in fl if f["serial_repeats"]["n"] and f["serial_repeats"]["pass"] == f["serial_repeats"]["n"]
                     ) if all(f["new_status"] == "pass" for f in fl) else "n/a"
        reps = sum(f["serial_repeats"]["n"] for f in fl)
        w(f"| {sname} | {t} | {sum(f['new_status'] == 'pass' for f in fl)} | {sum(f['new_status'] == 'fail' for f in fl)} | "
          f"{_q(ratios)} | {rep_ok} of {len(fl)} ({reps} repeats) |")
    w("")
    for s in summary:
        if s["count_changes"]:
            he = {r["id"]: r["per_task"].get("HumanEval/15") for r in s["records"]}
            w(f"- **{s['set']}** stored only counts, so flips are identified at count level: " + "; ".join(
                f"{c['key']} {c['old']} -> {c['new']} (HumanEval/15 serial: {'pass' if he.get(c['key']) else 'fail'})"
                for c in s["count_changes"]))
    w("")
    w("## Runs whose reported pass count changes\n")
    for s in summary:
        ch = [r for r in s["records"] if r["n_pass"] != r["old_n_pass"]]
        if ch:
            w(f"- **{s['set']}** ({len(ch)} of {len(s['records'])} runs): " + "; ".join(
                f"{r['id'] if r.get('setting') is None else r['id'] + '|' + r['setting']} {r['old_n_pass']}->{r['n_pass']}"
                for r in ch))
    nat = [r for s in summary if s["set"] == "native" for r in s["records"]]
    if nat:
        w("- native 15-task subset (old / serial): " + "; ".join(
            f"{r['id']} {r.get('old_n_pass_smoke15')} / {r.get('n_pass_smoke15')}" for r in nat))
    w("")
    if impact:
        w("## Census consequences (rules of paper-v3/analysis/numbers_v3.py, analyze.py unchanged)\n")
        w("| Scoring | Stage-one flags (<9 of 15) | Classes | Suspects | HF community >= 9 |")
        w("|---|---|---|---|---|")
        for k in ("original (audit_scored)", "pod rescore (census_rescore)", "serial"):
            v = impact[k]
            w(f"| {k} | {v['stage1_flags_lt9']} | {v['classes']} | {len(v['suspects'])}: {', '.join(v['suspects'])} | {v['community_ge9']} of 22 |")
        h = impact["he15_pass_official"]
        w(f"\nHumanEval/15 passes among the 305 official tags: original {h['original']}, pod rescore "
          f"{h['pod rescore']}, serial {h['serial']}. Official tags whose 15-task score differs from the pod "
          f"rescore: {impact['official_changed_vs_rescore']}; from the original census: "
          f"{impact['official_changed_vs_original']}.\n")
        fr = impact["full164"]
        w("Full 164-task census runs (old -> serial): " + "; ".join(
            f"{t} {v['old']}->{v['serial']}" for t, v in fr.items()) + "\n")
    w("## Pass-to-fail\n")
    p2f = [f for f in flips if f["new_status"] == "fail"]
    nsamp = sum(s["sample_pass"] for s in summary)
    if not p2f:
        w(f"None. No previously passing instance failed serially: 0 of the {nsamp} sampled passes, and none of "
          "the instances that passed in one existing scoring and failed in another (census HumanEval/15 and "
          "HumanEval/23 under the pod rescore) failed serially.\n")
    else:
        for f in p2f:
            w(f"- {f['set']} {f['key']} {f['task_id']}: {f['new_base_status']}/{f['new_plus_status']}; "
              f"{f['new_plus_reason']}; diagnosis {json.dumps(f.get('diagnosis'))[:400]}")
        w("")
    w("## Instances that still fail serially\n")
    w("Reasons recorded by EvalPlus for the re-evaluated failures that stay failures (base / plus): see "
      "`instances.jsonl` (`base_reason`, `plus_reason`). Counts by plus status: " + ", ".join(
        f"{k}: {v}" for k, v in sorted(Counter(x for s in summary for x in s.get("still_fail_status", [])).items())) + "\n")
    w("## Not scored\n")
    incomplete = [s for s in summary if s["incomplete"] or s["missing_transcripts"] or s["unattempted"]]
    if not incomplete:
        w("Nothing: every selected instance of every set was evaluated and no transcript is missing.\n")
    for s in incomplete:
        w(f"- {s['set']}: {s['incomplete']} selected instances not evaluated; {s['unattempted']} universe tasks "
          f"absent from the transcript (counted as fail, as the original scorer did); missing transcripts "
          f"{s['missing_transcripts']}")
    w(NOTES)
    w("## Commands\n")
    w("As run (2026-10-21; SERIAL_WORK pointed at a scratch directory; each command ran alone):\n")
    w("```")
    w("cd <scratch>/serial && export SERIAL_WORK=$PWD/work")
    w("S='.../paper-v3/analysis/serial/serial_rescore.py'")
    w("/usr/bin/python3 -E $S list")
    w("/usr/bin/python3 -E $S run metalrep      # pilot (33 instances), kept: the checkpoint resumes")
    w("/usr/bin/python3 -E $S run               # all sets in order, one process, one instance at a time")
    w("/usr/bin/python3 -E $S stability         # every flip again: 2x, or 5x if some test ran at >= 0.25 of its limit")
    w("/usr/bin/python3 -E $S report")
    w("```\n")
    w(f"Per transcript the sanitizer call is `{os.path.join(EVALPLUS_BIN, 'evalplus.sanitize')} --samples "
      "<SERIAL_WORK>/<set>/<sha1(run key)[:16]>/samples.jsonl` (164-task padded file, as the original scorers "
      "write it); its `samples-sanitized.jsonl` output is kept in the work directory.\n")
    w("Provenance next to this report: `instances.jsonl` (one line per serially evaluated instance: statuses, "
      "EvalPlus reasons, wall time, load average, flip diagnosis), `stability.jsonl` (repeats of flipped "
      "instances), `run_log.jsonl` (start/end per set with load averages), `serial_summary.json`.\n")
    open(os.path.join(OUT, "SERIAL_REPORT.md"), "w").write("\n".join(L) + "\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    names = [a for a in sys.argv[2:]] or SET_ORDER
    for n in names:
        if n not in SETS:
            sys.exit(f"unknown set {n}; known: {', '.join(SET_ORDER)}")
    {"list": cmd_list, "run": cmd_run, "stability": cmd_stability, "report": cmd_report}[cmd](names)


if __name__ == "__main__":
    main()
