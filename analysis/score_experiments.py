#!/usr/bin/env python3
"""Score the two review-mandated experiments.

A) results-native/     : deepseek artifacts run under their NATIVE embedded
                         template (164 tasks each) -> smoke-15 + full-164
B) results-sensitivity/: unflagged artifacts on 49 held-out tasks -> miss-rate
                         estimate for the screen

Writes analysis/experiments.json.
"""
import glob, json, os, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EV = os.path.expanduser("~/Library/Python/3.9/bin")
SUITE = set(json.load(open(os.path.join(ROOT, "smoke_suite_v1.json")))["suite_tasks"])
HELD = set(json.load(open(os.path.join(ROOT, "heldout_49.json"))))

def score(transcript, task_universe):
    from evalplus.data import get_human_eval_plus
    tasks = get_human_eval_plus()
    gens = {json.loads(l)["task_id"]: json.loads(l)["solution"]
            for l in open(transcript) if l.strip()}
    with tempfile.TemporaryDirectory() as td:
        sp = os.path.join(td, "s.jsonl")
        with open(sp, "w") as f:
            for tid in tasks:
                f.write(json.dumps({"task_id": tid, "solution": gens.get(tid, "pass")}) + "\n")
        env = dict(os.environ, PATH=os.environ["PATH"] + ":" + EV)
        subprocess.run([os.path.join(EV, "evalplus.sanitize"), "--samples", sp],
                       capture_output=True, env=env)
        san = sp.replace(".jsonl", "-sanitized.jsonl")
        san = san if os.path.exists(san) else sp
        subprocess.run([os.path.join(EV, "evalplus.evaluate"), "--dataset", "humaneval",
                        "--samples", san], capture_output=True, text=True, env=env, timeout=5400)
        rf = glob.glob(os.path.join(td, "*eval_results.json"))
        if not rf:
            return None
        ev = json.load(open(rf[0]))["eval"]
        passed = set()
        for tid, e in ev.items():
            x = e[0] if isinstance(e, list) else e
            if x.get("base_status") == "pass" and x.get("plus_status") == "pass":
                passed.add(tid)
        attempted = set(gens.keys()) & task_universe
        return {"passed_in_universe": len(passed & task_universe),
                "attempted": len(attempted),
                "passed_smoke": len(passed & SUITE),
                "passed_all164": len(passed)}

out = {"native": [], "sensitivity": []}

for tp in sorted(glob.glob(os.path.join(ROOT, "results-native", "transcripts", "*.jsonl"))):
    r = score(tp, set(json.load(open(os.path.join(ROOT, "heldout_49.json"))) ) | SUITE)
    name = os.path.basename(tp)
    rec = json.loads(open(os.path.join(ROOT, "results-native", "audit_results.jsonl")).readlines()[0])
    out["native"].append({"file": name, "smoke15": r["passed_smoke"],
                          "full164": r["passed_all164"]})
    print(f"NATIVE {name}: smoke {r['passed_smoke']}/15, full {r['passed_all164']}/164", flush=True)

for tp in sorted(glob.glob(os.path.join(ROOT, "results-sensitivity", "transcripts", "*.jsonl"))):
    r = score(tp, HELD)
    name = os.path.basename(tp).replace(".jsonl", "")
    rate = r["passed_in_universe"] / max(1, r["attempted"])
    out["sensitivity"].append({"artifact": name, "passed": r["passed_in_universe"],
                               "attempted": r["attempted"], "rate": round(rate, 3)})
    print(f"SENS {name}: {r['passed_in_universe']}/{r['attempted']} held-out ({rate:.0%})", flush=True)

json.dump(out, open(os.path.join(HERE, "experiments.json"), "w"), indent=1)
print("\nwrote analysis/experiments.json")
