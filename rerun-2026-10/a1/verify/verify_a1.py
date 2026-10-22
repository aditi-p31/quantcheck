#!/usr/bin/env python3
"""Independent check of analysis A1 (suite-size / task-choice justification).

Written from scratch; does not import or read the A1 code. Imports only the
helper functions (norm_model / norm_size / size_key / HIGH) from the paper's
own analyze.py so the family-size grouping is exactly the published one;
the classification branch of analyze.main() is re-stated below verbatim with
thresholds scaled to a k-task suite.

Run:  python3 -I verify_a1.py   (stdlib only; numpy is not installed)
Out:  verify_results.json next to this file.
"""
import sys
sys.dont_write_bytecode = True  # never write __pycache__ into the input tree

import glob, importlib.util, itertools, json, math, os, random, statistics
from collections import Counter, defaultdict

SEED = 20261021
HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.environ.get("QUANTCHECK_ROOT", os.path.abspath(os.path.join(HERE, "..", "..", "..")))
# P1 calibration evaluation files are not part of this repository; point QUANTCHECK_P1_RESULTS at them.
P1R = os.environ.get("QUANTCHECK_P1_RESULTS", os.path.join(P2, "p1_results"))
DEFECT_CFG = "qwen2.5-coder_3b-instruct-q3_K_M"
DEFECTS4 = ["qwen2.5-coder:3b-instruct-q2_K", "qwen2.5-coder:3b-instruct-q3_K_S",
            "qwen2.5-coder:3b-instruct-q3_K_M", "qwen2.5-coder:3b-instruct-q3_K_L"]
PHI = "phi3.5:3.8b-mini-instruct-q2_K"
DEFECTS5 = DEFECTS4 + [PHI]

spec = importlib.util.spec_from_file_location("p2_analyze", os.path.join(P2, "analysis", "analyze.py"))
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)

def popcount(x):
    return bin(x).count("1")

def tidnum(t):
    return int(t.split("/")[1])

out = {"seed": SEED, "python": sys.version.split()[0], "numpy": False}

# ---------------------------------------------------------------- part 1
def load_p1(bench):
    res = {}
    for f in sorted(glob.glob(os.path.join(P1R, "*.%s.samples-sanitized_eval_results.json" % bench))):
        cfg = os.path.basename(f).split("." + bench)[0]
        ev = json.load(open(f))["eval"]
        res[cfg] = {}
        for tid, samples in ev.items():
            assert len(samples) == 1, (f, tid)
            s = samples[0]
            res[cfg][tid] = (s["base_status"] == "pass" and s["plus_status"] == "pass")
    return res

he = load_p1("humaneval")
assert len(he) == 24 and DEFECT_CFG in he, sorted(he)
healthy = sorted(c for c in he if c != DEFECT_CFG)
tasks164 = sorted(next(iter(he.values())).keys(), key=tidnum)
assert len(tasks164) == 164 and all(len(he[c]) == 164 for c in he)
always = [t for t in tasks164 if all(he[c][t] for c in healthy)]
suite = json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"]
first15_lex = sorted(always)[:15]
first15_num = sorted(always, key=tidnum)[:15]
out["part1"] = {
    "n_configs": len(he), "n_healthy": len(healthy),
    "n_always_solved": len(always),
    "always_solved": sorted(always, key=tidnum),
    "suite_equals_first15_lexicographic": sorted(first15_lex) == sorted(suite),
    "suite_order_equals_lex_order": first15_lex == suite,
    "first15_numeric": first15_num,
    "overlap_numeric_vs_suite": len(set(first15_num) & set(suite)),
    "suite_subset_of_always": set(suite) <= set(always),
    "healthy_scores_on_suite": {c: sum(he[c][t] for t in suite) for c in healthy},
    "defect_score_on_suite": sum(he[DEFECT_CFG][t] for t in suite),
    "defect_score_on_164": sum(he[DEFECT_CFG].values()),
    "healthy_pass_HE15": sum(he[c]["HumanEval/15"] for c in healthy),
}

# ---------------------------------------------------------------- part 2
rows = [json.loads(l) for l in open(os.path.join(P2, "results", "audit_scored.jsonl")) if l.strip()]
off = [r for r in rows if r.get("channel") == "ollama-official"]
assert len(off) == 305 and len({r["tag"] for r in off}) == 305
assert all(sorted(r["per_task"]) == sorted(suite) for r in off)
assert all(r["smoke_pass"] == sum(r["per_task"].values()) for r in off)
TI = {t: i for i, t in enumerate(suite)}
mask = {r["tag"]: sum(1 << TI[t] for t, ok in r["per_task"].items() if ok) for r in off}
tags = [r["tag"] for r in off]
key = {t: an.size_key(t) for t in tags}
groups = defaultdict(list)
for t in tags:
    groups[key[t]].append(t)
hi_members = {k: [t for t in g if any(h in t for h in an.HIGH)] for k, g in groups.items()}

def classify(S, k):
    """S: bitmask of the k suite tasks in use. Returns (flags, classes).
    Stage one: s/k < 0.6 (k=15 -> s<9). Stage two exactly as analyze.main():
    healthy ratio>=0.6; suspect s<=2 and b>=8 (scaled: 15s<=2k, 15b>=8k);
    collapsed ratio<0.6 and b<8 (scaled 15b<8k); else degraded."""
    sc = {t: popcount(mask[t] & S) for t in tags}
    base = {kk: (statistics.median([sc[x] for x in hm]) if hm else None) for kk, hm in hi_members.items()}
    flags, classes = set(), {}
    for t in tags:
        s = sc[t]; b = base[key[t]]
        if 5 * s < 3 * k:
            flags.add(t)
        if b is None:
            classes[t] = "NO_BASELINE"; continue
        ratio = s / b if b else 0
        if ratio >= 0.6:
            classes[t] = "HEALTHY"
        elif 15 * s <= 2 * k and 15 * b >= 8 * k:
            classes[t] = "DEFECT_SUSPECT"
        elif ratio < 0.6 and 15 * b < 8 * k:
            classes[t] = "COLLAPSED"
        else:
            classes[t] = "DEGRADED"
    return flags, classes

def jac(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)

FULL = (1 << 15) - 1
F_flags, F_cls = classify(FULL, 15)
F_susp = {t for t, c in F_cls.items() if c == "DEFECT_SUSPECT"}
findings = json.load(open(os.path.join(P2, "analysis", "findings.json")))
out["part2_full_suite"] = {
    "n_flags": len(F_flags), "n_suspects": len(F_susp), "suspects": sorted(F_susp),
    "class_counts": dict(Counter(F_cls.values())),
    "matches_findings_json": dict(Counter(F_cls.values())) == findings["class_distribution"],
    "HE15_pass_count_official": sum(r["per_task"]["HumanEval/15"] for r in off),
    "HE15_pass_count_all_rows": sum(r["per_task"].get("HumanEval/15", False) for r in rows),
}

def curve(pool_idx, ks):
    res = {}
    for k in ks:
        n = fl_sum = 0
        jf = js = 0.0
        c4 = c5 = c4f = c5f = 0
        recall = 0.0
        lost = Counter()
        for comb in itertools.combinations(pool_idx, k):
            S = sum(1 << i for i in comb)
            fl, cl = classify(S, k)
            su = {t for t, c in cl.items() if c == "DEFECT_SUSPECT"}
            n += 1; fl_sum += len(fl)
            jf += jac(fl, F_flags); js += jac(su, F_susp)
            recall += len(fl & F_flags) / len(F_flags)
            c4 += all(d in su for d in DEFECTS4); c5 += all(d in su for d in DEFECTS5)
            c4f += all(d in fl for d in DEFECTS4); c5f += all(d in fl for d in DEFECTS5)
            for t in F_susp - su:
                lost[t] += 1
        res[str(k)] = {"n_subsets": n, "mean_flags": round(fl_sum / n, 3),
                       "mean_jaccard_flags": round(jf / n, 4), "mean_recall_flags": round(recall / n, 4),
                       "mean_jaccard_suspects": round(js / n, 4),
                       "frac_all4_suspect": round(c4 / n, 4), "frac_all5_suspect": round(c5 / n, 4),
                       "frac_all4_flagged": round(c4f / n, 4), "frac_all5_flagged": round(c5f / n, 4),
                       "suspects_lost_counts": dict(lost)}
    return res

out["part2_curve_15"] = curve(list(range(15)), list(range(3, 16)))
live = [TI[t] for t in suite if t != "HumanEval/15"]
out["part2_curve_14live"] = curve(live, list(range(3, 15)))

# ---------------------------------------------------------------- part 3
TI164 = {t: i for i, t in enumerate(tasks164)}
cmask = {c: sum(1 << TI164[t] for t, ok in he[c].items() if ok) for c in he}
def hyper_p_lt(K, N=164, n=15, thr=9):
    return sum(math.comb(K, x) * math.comb(N - K, n - x) for x in range(0, thr)) / math.comb(N, n)
per_cfg_exact = {c: round(hyper_p_lt(popcount(cmask[c])), 4) for c in healthy}

# calibration two-stage baseline: median of q6_K, q8_0, fp16 within size
def csize(c):
    return c.split("_")[1].split("-")[0]
chi = defaultdict(list)
for c in healthy:
    if any(h in c for h in ("q6_K", "q8_0", "fp16")):
        chi[csize(c)].append(c)

def draw_stats(N, rng):
    any_flag = 0; per = Counter(); any_nonhealthy2 = any_susp2 = defect_susp = 0
    min_scores = []
    for _ in range(N):
        idx = rng.sample(range(164), 15)
        S = sum(1 << i for i in idx)
        sc = {c: popcount(cmask[c] & S) for c in he}
        fl = [c for c in healthy if sc[c] < 9]
        any_flag += bool(fl)
        for c in fl:
            per[c] += 1
        min_scores.append(min(sc[c] for c in healthy))
        base = {z: statistics.median([sc[c] for c in chi[z]]) for z in chi}
        nh = su = False
        for c in he:
            s = sc[c]; b = base[csize(c)]
            ratio = s / b if b else 0
            if ratio >= 0.6:
                cls = "H"
            elif s <= 2 and b >= 8:
                cls = "S"
            else:
                cls = "X"
            if c == DEFECT_CFG:
                defect_susp += cls == "S"
            else:
                nh |= cls != "H"; su |= cls == "S"
        any_nonhealthy2 += nh; any_susp2 += su
    return any_flag, per, any_nonhealthy2, any_susp2, defect_susp, min_scores

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]

rng = random.Random(SEED)
p3 = {}
for N in (2000, 100000):
    af, per, nh2, su2, ds, mins = draw_stats(N, rng)
    ms = sorted(mins)
    p3[str(N)] = {"frac_suites_flag_any_healthy_stage1": round(af / N, 4), "wilson95": wilson(af, N),
                  "per_config_flag_rate": {c: round(per[c] / N, 4) for c in healthy},
                  "frac_any_healthy_not_HEALTHY_after_stage2": round(nh2 / N, 4),
                  "frac_any_healthy_DEFECT_SUSPECT_after_stage2": round(su2 / N, 4),
                  "frac_defect_cfg_DEFECT_SUSPECT": round(ds / N, 4),
                  "min_healthy_score_mean": round(sum(mins) / N, 3),
                  "min_healthy_score_p5_p95": [ms[int(0.05 * N)], ms[int(0.95 * N) - 1]]}
out["part3"] = {"per_config_exact_P_flag": per_cfg_exact,
                "healthy_pass_counts_164": {c: popcount(cmask[c]) for c in healthy},
                "high_precision_baseline_members": dict(chi), "mc": p3}

json.dump(out, open(os.path.join(HERE, "verify_results.json"), "w"), indent=1, sort_keys=True)
print(json.dumps({k: v for k, v in out.items() if k not in ("part2_curve_15", "part2_curve_14live")}, indent=1)[:6000])
for name in ("part2_curve_15", "part2_curve_14live"):
    print(name)
    for k, v in out[name].items():
        print(" k=%2s n=%5d flags=%6.2f Jf=%.3f recall=%.3f Js=%.3f all4=%.4f all5=%.4f lost=%s" % (
            k, v["n_subsets"], v["mean_flags"], v["mean_jaccard_flags"], v["mean_recall_flags"],
            v["mean_jaccard_suspects"], v["frac_all4_suspect"], v["frac_all5_suspect"], v["suspects_lost_counts"]))
