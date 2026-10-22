#!/usr/bin/env python3
"""A1: suite-size and task-choice sensitivity of the 15-task smoke screen.

Answers BigData Reviewer 2, point 2 ("no justification for 15 tasks; compare
suite sizes / combinations") from EXISTING data only. No model is run.

Parts
  1  Census suite-size curve: k-subsets (k = 3..15) of the 15 suite tasks,
     two-stage screen re-run on each subset with constants scaled to k.
  2  Task-choice sensitivity at k = 15 on the P1 calibration data
     (24 Qwen2.5-Coder configs, full HumanEval+).
  3  MBPP+ cross-check on the calibration configs.
  1v Variant of part 1 restricted to suite tasks that at least one census
     artifact passes (HumanEval/15 is passed by none of the 305).
  S  Supplementary: census-vs-calibration agreement on the 15 suite tasks,
     per-task census pass rates.

Screening logic is taken from analysis/analyze.py (the code that produced
findings.json and the paper's numbers). Its helper functions (size_key,
norm_model, norm_size, HIGH) are executed from the original source file so
the grouping is byte-for-byte the released logic; the inline classification
rule is transcribed below and checked against findings.json at k = 15.

Scaling of the fixed constants to a k-task suite (exact rationals, no rounding):
  stage one flag          s < 0.6 k          <=>  5 s <  3 k   (k=15: s < 9)
  stage two healthy       s / b >= 0.6        (ratio; unchanged)
  defect suspect          s <= (2/15) k  AND  b >= (8/15) k
                          <=> 15 s <= 2 k  AND  15 b >= 8 k     (k=15: s<=2, b>=8)
  capability collapse     s / b < 0.6  AND  15 b < 8 k
  degraded                everything else with a baseline
  no baseline             model+size group has no q6_K / q8_0 / fp16 build
where s is the artifact's pass count on the subset and b is the median pass
count, on the same subset, of the artifact's high-precision siblings.

Run:  python3 -I a1_analysis.py            (writes a1_results.json next to it)
      python3 -I a1_analysis.py --tables   (also prints Markdown tables)

Standard library only (numpy is not installed on this machine; checked).
"""
import glob
import hashlib
import itertools
import json
import math
import os
import platform
import random
import statistics
import sys
from collections import Counter, defaultdict

SEED = 20261021
N_DRAWS = 1000

HERE = os.path.dirname(os.path.abspath(__file__))
# Paths are configurable (QUANTCHECK_ROOT = repository root; default: two levels above this file).
P2 = os.environ.get("QUANTCHECK_ROOT", os.path.abspath(os.path.join(HERE, "..", "..")))
CENSUS = os.path.join(P2, "results", "audit_scored.jsonl")
SUITE_FILE = os.path.join(P2, "smoke_suite_v1.json")
ANALYZE_PY = os.path.join(P2, "analysis", "analyze.py")
CLASSIFY_PY = os.path.join(P2, "analysis", "classify.py")
FINDINGS = os.path.join(P2, "analysis", "findings.json")
# P1 calibration evaluation files are not part of this repository; point QUANTCHECK_P1_RESULTS at them.
P1_RES = os.environ.get("QUANTCHECK_P1_RESULTS", os.path.join(P2, "p1_results"))
OUT_JSON = os.path.join(HERE, "a1_results.json")
CENSUS_TGZ = os.path.join(P2, "results", "audit_data_full.tgz")   # read in memory only

CONFIRMED_4 = [
    "qwen2.5-coder:3b-instruct-q2_K",
    "qwen2.5-coder:3b-instruct-q3_K_S",
    "qwen2.5-coder:3b-instruct-q3_K_M",
    "qwen2.5-coder:3b-instruct-q3_K_L",
]
PHI = "phi3.5:3.8b-mini-instruct-q2_K"
CONFIRMED_5 = CONFIRMED_4 + [PHI]
CAL_DEFECTIVE = "qwen2.5-coder_3b-instruct-q3_K_M"   # P1 file stem of the known defect

POP = [bin(i).count("1") for i in range(1 << 15)]   # popcount table, 15-bit masks


# ---------------------------------------------------------------- helpers
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(xs, q):
    """Percentile with linear interpolation between order statistics
    (Hyndman-Fan type 7, numpy's default)."""
    xs = sorted(xs)
    n = len(xs)
    if n == 1:
        return float(xs[0])
    h = (n - 1) * q
    lo = int(math.floor(h))
    hi = min(lo + 1, n - 1)
    return float(xs[lo] + (h - lo) * (xs[hi] - xs[lo]))


def summ(xs, nd=3):
    return {"mean": round(statistics.fmean(xs), nd), "p5": round(pct(xs, 0.05), nd),
            "p50": round(pct(xs, 0.50), nd), "p95": round(pct(xs, 0.95), nd),
            "min": min(xs), "max": max(xs)}


def jaccard(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def spearman(x, y):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for t in range(i, j + 1):
                r[order[t]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def load_analyze_helpers():
    """Execute analysis/analyze.py's source in a private namespace (its main()
    is guarded and does not run; nothing is written to the input folder)."""
    src = open(ANALYZE_PY).read()
    ns = {"__name__": "analyze_src", "__file__": ANALYZE_PY}
    exec(compile(src, ANALYZE_PY, "exec"), ns)
    return ns


# ------------------------------------------------- generalized classifier
def stage_one_flag(s, k):
    return 5 * s < 3 * k                       # s < 0.6 k


def stage_two(s, b, k):
    """analyze.py rule, with 2/15 and 8/15 scaled proportionally to k."""
    if b is None:
        return "NO_BASELINE"
    ratio = s / b if b else 0                  # as in analyze.py
    if ratio >= 0.6:
        return "HEALTHY"
    elif 15 * s <= 2 * k and 15 * b >= 8 * k:  # s <= 2k/15 and b >= 8k/15
        return "DEFECT_SUSPECT"
    elif ratio < 0.6 and 15 * b < 8 * k:       # b < 8k/15
        return "COLLAPSED"
    else:
        return "DEGRADED"


def analyze_py_literal(s, b):
    """Literal transcription of analyze.py main() lines 'classify' (k = 15)."""
    if b is None:
        return "NO_BASELINE"
    ratio = s / b if b else 0
    if ratio >= 0.6:
        return "HEALTHY"
    elif s <= 2 and b >= 8:
        return "DEFECT_SUSPECT"
    elif ratio < 0.6 and b < 8:
        return "COLLAPSED"
    else:
        return "DEGRADED"


# ------------------------------------------------------------ Part 1
def part1(ns, suite, official, tables):
    size_key, HIGH = ns["size_key"], ns["HIGH"]
    n = len(official)
    tags = [r["tag"] for r in official]
    idx = {t: i for i, t in enumerate(tags)}
    masks = [sum(1 << j for j, t in enumerate(suite) if r["per_task"][t]) for r in official]
    gkey = [size_key(t) for t in tags]
    groups = defaultdict(list)
    for i, r in enumerate(official):
        groups[gkey[i]].append(i)
    # high-precision siblings, exactly as analyze.py selects them
    hp = {g: [i for i in members if any(h in tags[i] for h in HIGH)]
          for g, members in groups.items()}

    def screen(sub_mask, k):
        scores = [POP[m & sub_mask] for m in masks]
        base = {g: (statistics.median([scores[i] for i in hp[g]]) if hp[g] else None)
                for g in groups}
        flagged = {i for i in range(n) if stage_one_flag(scores[i], k)}
        cls = {i: stage_two(scores[i], base[gkey[i]], k) for i in flagged}
        return scores, base, flagged, cls

    full_mask = (1 << 15) - 1
    scores15, base15, flag15, cls15 = screen(full_mask, 15)
    susp15 = {i for i, c in cls15.items() if c == "DEFECT_SUSPECT"}

    # ---- verification against analyze.py / findings.json at k = 15
    findings = json.load(open(FINDINGS))
    all_cls_general = Counter(stage_two(scores15[i], base15[gkey[i]], 15) for i in range(n))
    all_cls_literal = Counter(analyze_py_literal(official[i]["smoke_pass"], base15[gkey[i]])
                              for i in range(n))
    findings_susp = {e["tag"] for e in findings["confirmed_defects"] + findings["cleared_as_capability"]}
    verification = {
        "smoke_pass_equals_sum_per_task": all(scores15[i] == official[i]["smoke_pass"] for i in range(n)),
        "class_distribution_all_305_generalized_rule": dict(all_cls_general),
        "class_distribution_all_305_literal_analyze_py": dict(all_cls_literal),
        "class_distribution_findings_json": findings["class_distribution"],
        "matches_findings_json": dict(all_cls_general) == findings["class_distribution"]
                                 == dict(all_cls_literal),
        "stage_one_flags_full_suite": len(flag15),
        "suspects_full_suite": sorted(tags[i] for i in susp15),
        "suspect_set_matches_findings_json": {tags[i] for i in susp15} == findings_susp,
        "unflagged_artifacts_all_healthy_or_no_baseline_under_all_artifact_rule":
            all(stage_two(scores15[i], base15[gkey[i]], 15) in ("HEALTHY", "NO_BASELINE")
                for i in range(n) if i not in flag15),
    }
    assert verification["smoke_pass_equals_sum_per_task"]
    assert verification["matches_findings_json"], verification
    assert verification["suspect_set_matches_findings_json"]
    assert len(flag15) == 50 and len(susp15) == 7

    flagged_full_classes = Counter(cls15.values())
    no_baseline_groups = sorted("/".join(g) for g in groups if not hp[g])
    full_ref = {
        "flags": sorted(tags[i] for i in flag15),
        "stage_two_classes_of_flagged": dict(flagged_full_classes),
        "suspects": sorted(tags[i] for i in susp15),
        "no_baseline_groups": no_baseline_groups,
        "n_no_baseline_artifacts": sum(len(groups[g]) for g in groups if not hp[g]),
        "baselines_of_confirmed": {t: base15[gkey[idx[t]]] for t in CONFIRMED_5},
        "high_precision_siblings_of_confirmed": {
            t: sorted(tags[j] for j in hp[gkey[idx[t]]]) for t in CONFIRMED_5},
    }

    c4 = {idx[t] for t in CONFIRMED_4}
    c5 = {idx[t] for t in CONFIRMED_5}

    def curve(pool, rng, detail_k=None):
        """Suite-size curve for k-subsets of the suite positions in `pool`."""
        per_k, detail = [], []
        for k in range(3, len(pool) + 1):
            combos = list(itertools.combinations(pool, k))
            enumerated = len(combos) <= N_DRAWS
            subsets = combos if enumerated else rng.sample(combos, N_DRAWS)
            nf, jf, rf, newf, ns_, js, all4, all5, exact = [], [], [], [], [], [], [], [], []
            extra_n, lost_n, nonconf4, nonconf5 = [], [], [], []
            retain = Counter()
            flag_retain5 = 0
            extra_ctr, lost_ctr = Counter(), Counter()
            cls_ctr = Counter()
            for sub in subsets:
                m = sum(1 << j for j in sub)
                _, _, flg, cls = screen(m, k)
                sus = {i for i, c in cls.items() if c == "DEFECT_SUSPECT"}
                nf.append(len(flg))
                jf.append(jaccard(flg, flag15))
                rf.append(len(flg & flag15) / len(flag15))
                newf.append(len(flg - flag15))
                ns_.append(len(sus))
                js.append(jaccard(sus, susp15))
                all4.append(c4 <= sus)
                all5.append(c5 <= sus)
                exact.append(sus == susp15)
                extra_n.append(len(sus - susp15))
                lost_n.append(len(susp15 - sus))
                nonconf4.append(len(sus - c4))
                nonconf5.append(len(sus - c5))
                flag_retain5 += c5 <= flg
                for i in c5:
                    retain[tags[i]] += i in sus
                for i in sus - susp15:
                    extra_ctr[tags[i]] += 1
                for i in susp15 - sus:
                    lost_ctr[tags[i]] += 1
                cls_ctr.update(cls.values())
                if k == detail_k:
                    dropped = [suite[j] for j in pool if j not in sub]
                    detail.append({
                        "dropped_tasks": dropped, "n_flags": len(flg),
                        "flags_added": sorted(tags[i] for i in flg - flag15),
                        "flags_removed": sorted(tags[i] for i in flag15 - flg),
                        "suspects": sorted(tags[i] for i in sus),
                        "suspect_set_unchanged": sus == susp15})
            S = len(subsets)
            smin = -(-3 * k // 5)                  # smallest unflagged score, ceil(0.6k)
            per_k.append({
                "k": k, "n_subsets": S, "n_possible": len(combos), "enumerated": enumerated,
                "stage_one_rule": f"flag iff s < {3 * k / 5:g}; unflagged needs s >= {smin} "
                                  f"({100 * smin / k:.1f}% of k)",
                "effective_pass_fraction_to_stay_unflagged": round(smin / k, 4),
                "suspect_rule": f"s <= {2 * k / 15:.3f} and b >= {8 * k / 15:.3f}",
                "n_flags": summ(nf, 2),
                "jaccard_flags_vs_full": summ(jf, 3),
                "recall_of_full_suite_flags": summ(rf, 3),
                "flags_not_in_full_set": summ(newf, 2),
                "n_suspects": summ(ns_, 2),
                "jaccard_suspects_vs_full": summ(js, 3),
                "frac_suspect_set_identical_to_full": round(sum(exact) / S, 4),
                "frac_all_4_confirmed_are_suspects": round(sum(all4) / S, 4),
                "frac_all_5_confirmed_incl_phi35_are_suspects": round(sum(all5) / S, 4),
                "frac_all_5_confirmed_flagged_stage_one": round(flag_retain5 / S, 4),
                "per_defect_suspect_rate": {t: round(retain[t] / S, 4) for t in CONFIRMED_5},
                "mean_suspects_not_in_full_set": round(statistics.fmean(extra_n), 3),
                "mean_full_suspects_lost": round(statistics.fmean(lost_n), 3),
                "mean_suspects_not_confirmed_4def": round(statistics.fmean(nonconf4), 3),
                "mean_suspects_not_confirmed_5def": round(statistics.fmean(nonconf5), 3),
                "top_extra_suspects": [[t, round(c / S, 4)] for t, c in extra_ctr.most_common(6)],
                "lost_full_suspects": [[t, round(c / S, 4)] for t, c in lost_ctr.most_common()],
                "mean_stage_two_classes_of_flagged": {c: round(v / S, 3) for c, v in sorted(cls_ctr.items())},
            })

        def first_k(pred):
            for r in per_k:
                if all(pred(rr) for rr in per_k if rr["k"] >= r["k"]):
                    return r["k"]
            return None
        thresholds = {
            "min_k_mean_jaccard_flags_ge_0.90": first_k(lambda r: r["jaccard_flags_vs_full"]["mean"] >= 0.90),
            "min_k_mean_recall_full_flags_ge_0.90": first_k(lambda r: r["recall_of_full_suite_flags"]["mean"] >= 0.90),
            "min_k_mean_jaccard_suspects_ge_0.90": first_k(lambda r: r["jaccard_suspects_vs_full"]["mean"] >= 0.90),
            "min_k_all4_retained_ge_0.95": first_k(lambda r: r["frac_all_4_confirmed_are_suspects"] >= 0.95),
            "min_k_all5_retained_ge_0.95": first_k(lambda r: r["frac_all_5_confirmed_incl_phi35_are_suspects"] >= 0.95),
            "min_k_suspect_set_identical_ge_0.95": first_k(lambda r: r["frac_suspect_set_identical_to_full"] >= 0.95),
            "note": "smallest k such that the criterion holds at that k and every larger k",
        }
        return per_k, detail, thresholds

    # primary curve: subsets of all 15 suite tasks (part-1 RNG stream, k = 3..15 in order)
    per_k, k14_detail, thresholds = curve(list(range(15)), random.Random(SEED), detail_k=14)
    # robustness variant: subsets of the suite tasks that at least one census artifact
    # passes (HumanEval/15 is passed by none of the 305), separate stream seeded with SEED
    live = [j for j, t in enumerate(suite) if any(masks[i] >> j & 1 for i in range(n))]
    dead = [suite[j] for j in range(15) if j not in live]
    per_k_live, _, thresholds_live = curve(live, random.Random(SEED))

    # per-task census pass rates (supplementary)
    per_task = []
    unflagged = [i for i in range(n) if i not in flag15]
    for j, t in enumerate(suite):
        per_task.append({"task": t,
                         "pass_rate_all_305": round(sum(bool(masks[i] >> j & 1) for i in range(n)) / n, 4),
                         "pass_rate_unflagged_255": round(sum(bool(masks[i] >> j & 1) for i in unflagged) / len(unflagged), 4),
                         "pass_rate_flagged_50": round(sum(bool(masks[i] >> j & 1) for i in flag15) / len(flag15), 4)})

    if tables:
        for label, rows_ in (("all 15 suite tasks", per_k), (f"live tasks only (excluding {dead})", per_k_live)):
            print(f"\n### Part 1: census suite-size curve, subsets of {label}\n")
            print("| k | subsets | stay-unflagged bar | flags mean [p5, p95] | recall of 50 full flags mean [p5] "
                  "| Jaccard flags mean [p5, p95] | suspects mean [p5, p95] | Jaccard suspects mean [p5, p95] "
                  "| suspect set identical | all 4 defects suspects | all 5 (incl. phi3.5) suspects |")
            print("|---|---|---|---|---|---|---|---|---|---|---|")
            for r in rows_:
                a, b, c, d, e = (r["n_flags"], r["jaccard_flags_vs_full"], r["n_suspects"],
                                 r["jaccard_suspects_vs_full"], r["recall_of_full_suite_flags"])
                smin = round(r["effective_pass_fraction_to_stay_unflagged"] * r["k"])
                print(f"| {r['k']} | {r['n_subsets']}{'*' if r['enumerated'] else ''} "
                      f"| {smin}/{r['k']} ({100 * r['effective_pass_fraction_to_stay_unflagged']:.0f}%) "
                      f"| {a['mean']:.1f} [{a['p5']:.0f}, {a['p95']:.0f}] "
                      f"| {e['mean']:.3f} [{e['p5']:.3f}] "
                      f"| {b['mean']:.3f} [{b['p5']:.3f}, {b['p95']:.3f}] "
                      f"| {c['mean']:.2f} [{c['p5']:.0f}, {c['p95']:.0f}] "
                      f"| {d['mean']:.3f} [{d['p5']:.3f}, {d['p95']:.3f}] "
                      f"| {r['frac_suspect_set_identical_to_full']:.3f} "
                      f"| {r['frac_all_4_confirmed_are_suspects']:.3f} "
                      f"| {r['frac_all_5_confirmed_incl_phi35_are_suspects']:.3f} |")
            print("\n| k | mean extra suspects | mean lost suspects | lost (rate) | non-confirmed suspects (4-def) | (5-def) | most frequent extra suspect | phi3.5 q2_K suspect rate |")
            print("|---|---|---|---|---|---|---|---|")
            for r in rows_:
                top = r["top_extra_suspects"][0] if r["top_extra_suspects"] else ["-", 0]
                lost = "; ".join(f"{t.split(':')[0]}:{t.split(':')[1]} {v:.2f}" for t, v in r["lost_full_suspects"]) or "-"
                print(f"| {r['k']} | {r['mean_suspects_not_in_full_set']:.2f} | {r['mean_full_suspects_lost']:.2f} | {lost} "
                      f"| {r['mean_suspects_not_confirmed_4def']:.2f} | {r['mean_suspects_not_confirmed_5def']:.2f} "
                      f"| {top[0]} ({top[1]:.2f}) | {r['per_defect_suspect_rate'][PHI]:.3f} |")
        print("\nk=14 leave-one-out (all 15 tasks):")
        for d in k14_detail:
            print(" ", d["dropped_tasks"], d["n_flags"], "+", len(d["flags_added"]), "-", len(d["flags_removed"]),
                  "susp_same" if d["suspect_set_unchanged"] else d["suspects"])
        print("\nthresholds:", thresholds)
        print("thresholds live:", thresholds_live)
        print("dead tasks:", dead)

    return {"verification": verification, "full_suite_reference": full_ref,
            "per_k": per_k, "k14_leave_one_out": k14_detail,
            "stability_thresholds": thresholds,
            "census_tasks_passed_by_no_artifact": dead,
            "variant_live_tasks_only": {
                "pool": [suite[j] for j in live],
                "note": "same procedure, subsets drawn only from suite tasks passed by at least "
                        "one census artifact; reference sets are still the full 15-task results",
                "per_k": per_k_live, "stability_thresholds": thresholds_live},
            "census_per_task_pass_rates": per_task}


# ------------------------------------------------------------ Part 2/3
def load_p1(kind):
    out = {}
    for f in sorted(glob.glob(os.path.join(P1_RES, f"*.{kind}.samples-sanitized_eval_results.json"))):
        cfg = os.path.basename(f).split(f".{kind}.")[0]
        ev = json.load(open(f))["eval"]
        # a task passes only if base_status and plus_status are both "pass"
        out[cfg] = {t: all(s["base_status"] == "pass" and s["plus_status"] == "pass" for s in v)
                    for t, v in ev.items()}
    return out


def part2_3(suite, official, tables):
    he = load_p1("humaneval")
    mb = load_p1("mbpp")
    cfgs = sorted(he)
    assert len(cfgs) == 24 and sorted(mb) == cfgs, (len(cfgs), sorted(mb))
    assert CAL_DEFECTIVE in he
    healthy = [c for c in cfgs if c != CAL_DEFECTIVE]
    all_tasks = sorted(next(iter(he.values())))
    assert all(sorted(he[c]) == all_tasks for c in cfgs) and len(all_tasks) == 164
    n_mbpp = {c: len(mb[c]) for c in cfgs}

    # (a) tasks solved by every healthy config
    pool39 = sorted(t for t in all_tasks if all(he[c][t] for c in healthy))
    lex15 = pool39[:15]
    num15 = sorted(pool39, key=lambda t: int(t.split("/")[1]))[:15]
    a = {
        "n_calibration_configs": len(cfgs), "n_healthy": len(healthy),
        "known_defective_config": CAL_DEFECTIVE,
        "n_tasks_solved_by_all_healthy": len(pool39),
        "is_39": len(pool39) == 39,
        "tasks_solved_by_all_healthy": pool39,
        "suite_equals_first_15_lexicographic": lex15 == suite,
        "first_15_numeric_order": num15,
        "overlap_suite_vs_first_15_numeric": len(set(num15) & set(suite)),
        "note": "'first 15 by identifier' holds for string (lexicographic) order of the "
                "task IDs, e.g. 'HumanEval/107' < 'HumanEval/11'; numeric order would pick a "
                "different set",
        "healthy_suite_scores": {c: sum(he[c][t] for t in suite) for c in healthy},
        "defective_suite_score": sum(he[CAL_DEFECTIVE][t] for t in suite),
        "defective_full_humaneval_plus_pass": sum(he[CAL_DEFECTIVE].values()),
    }
    a["all_healthy_15_of_15"] = all(v == 15 for v in a["healthy_suite_scores"].values())

    # (b), (c) alternative suites
    def eval_suite(tasks):
        hs = [sum(he[c][t] for t in tasks) for c in healthy]
        return {"healthy_min": min(hs), "healthy_median": statistics.median(hs),
                "n_healthy_flagged": sum(stage_one_flag(s, 15) for s in hs),
                "flagged_healthy": [c for c, s in zip(healthy, hs) if stage_one_flag(s, 15)],
                "defective": sum(he[CAL_DEFECTIVE][t] for t in tasks)}

    rng = random.Random(SEED)       # part-2 stream: 39-pool draws first, then 164-pool
    pools = {"pool39": pool39, "pool164": all_tasks}
    b = {}
    for name, pool in pools.items():
        draws = [tuple(sorted(rng.sample(pool, 15))) for _ in range(N_DRAWS)]
        res = [eval_suite(d) for d in draws]
        S = len(res)
        k_any = sum(r["n_healthy_flagged"] > 0 for r in res)
        p, lo, hi = wilson(k_any, S)
        per_cfg = Counter(c for r in res for c in r["flagged_healthy"])
        b[name] = {
            "pool_size": len(pool), "n_suites": S, "n_distinct_suites": len(set(draws)),
            "healthy_min": summ([r["healthy_min"] for r in res], 2),
            "healthy_median": summ([r["healthy_median"] for r in res], 2),
            "healthy_min_distribution": dict(sorted(Counter(r["healthy_min"] for r in res).items())),
            "defective_score": summ([r["defective"] for r in res], 2),
            "defective_score_available": True,
            "frac_suites_all_healthy_15_of_15": round(sum(r["healthy_min"] == 15 for r in res) / S, 4),
            "frac_suites_flagging_ge1_healthy": round(p, 4),
            "frac_suites_flagging_ge1_healthy_wilson95": [round(lo, 4), round(hi, 4)],
            "n_healthy_flagged_per_suite": summ([r["n_healthy_flagged"] for r in res], 2),
            "frac_suites_defective_flagged": round(sum(stage_one_flag(r["defective"], 15) for r in res) / S, 4),
            "frac_suites_perfect_separation_at_60pct": round(
                sum(r["n_healthy_flagged"] == 0 and stage_one_flag(r["defective"], 15) for r in res) / S, 4),
            "per_config_flag_rate": {c: round(per_cfg[c] / S, 4) for c in healthy},
        }

    # Part 3: MBPP+ cross-check
    p3 = []
    for c in cfgs:
        hp_ = sum(he[c].values())
        mp = sum(mb[c].values())
        p3.append({"config": c, "healthy": c != CAL_DEFECTIVE,
                   "suite_score_calibration": sum(he[c][t] for t in suite),
                   "humaneval_plus_pass": hp_, "humaneval_plus_rate": round(hp_ / 164, 4),
                   "mbpp_plus_pass": mp, "mbpp_plus_n": n_mbpp[c], "mbpp_plus_rate": round(mp / n_mbpp[c], 4)})
    hrows = [r for r in p3 if r["healthy"]]
    p3_summary = {
        "healthy_mbpp_plus_rate": summ([r["mbpp_plus_rate"] for r in hrows], 4),
        "healthy_humaneval_plus_rate": summ([r["humaneval_plus_rate"] for r in hrows], 4),
        "defective_mbpp_plus": [r for r in p3 if not r["healthy"]][0],
        "spearman_he_vs_mbpp_healthy": round(spearman([r["humaneval_plus_rate"] for r in hrows],
                                                      [r["mbpp_plus_rate"] for r in hrows]), 3),
    }

    # Supplementary: same artifacts in the census run vs the calibration run
    by_tag = {r["tag"]: r for r in official}
    overlap = []
    for c in cfgs:
        tag = c.replace("_", ":", 1)
        r = by_tag.get(tag)
        cal = {t: he[c][t] for t in suite}
        if r is None:
            overlap.append({"config": tag, "in_census": False, "calibration_suite": sum(cal.values())})
            continue
        dis = sorted(t for t in suite if bool(r["per_task"][t]) != cal[t])
        overlap.append({"config": tag, "in_census": True, "calibration_suite": sum(cal.values()),
                        "census_smoke": r["smoke_pass"], "n_task_disagreements": len(dis),
                        "disagreeing_tasks": dis})
    inc = [o for o in overlap if o["in_census"]]
    overlap_summary = {
        "n_in_census": len(inc),
        "n_identical_per_task": sum(o["n_task_disagreements"] == 0 for o in inc),
        "n_healthy_scoring_below_15_in_census": sum(o["census_smoke"] < 15 for o in inc
                                                    if o["config"] != CAL_DEFECTIVE.replace("_", ":", 1)),
        "min_census_smoke_healthy": min(o["census_smoke"] for o in inc
                                        if o["config"] != CAL_DEFECTIVE.replace("_", ":", 1)),
        "any_healthy_flagged_in_census": any(o["census_smoke"] < 9 for o in inc
                                             if o["config"] != CAL_DEFECTIVE.replace("_", ":", 1)),
        "task_disagreement_counts": dict(Counter(t for o in inc for t in o["disagreeing_tasks"]).most_common()),
    }

    if tables:
        print("\n### Part 2\n", json.dumps({k: v for k, v in a.items() if k != "tasks_solved_by_all_healthy"}, indent=1))
        for name in pools:
            x = b[name]
            print(f"\n{name}: healthy_min {x['healthy_min']}  healthy_median {x['healthy_median']}  "
                  f"defective {x['defective_score']}  flag>=1 healthy {x['frac_suites_flagging_ge1_healthy']} "
                  f"{x['frac_suites_flagging_ge1_healthy_wilson95']}  n flagged {x['n_healthy_flagged_per_suite']} "
                  f"all15 {x['frac_suites_all_healthy_15_of_15']} distinct {x['n_distinct_suites']}")
            print("  min dist", x["healthy_min_distribution"])
            print("  per-config flag rate", {k.split("_", 1)[1]: v for k, v in x["per_config_flag_rate"].items() if v})
        print("\n### Part 3\n| config | suite (cal.) | HumanEval+ | MBPP+ |\n|---|---|---|---|")
        for r in p3:
            print(f"| {r['config'].replace('_', ':', 1)}{'' if r['healthy'] else ' (defective)'} "
                  f"| {r['suite_score_calibration']}/15 | {r['humaneval_plus_pass']}/164 ({100 * r['humaneval_plus_rate']:.1f}%) "
                  f"| {r['mbpp_plus_pass']}/{r['mbpp_plus_n']} ({100 * r['mbpp_plus_rate']:.1f}%) |")
        print(p3_summary)
        print("\n### Supplementary overlap\n", json.dumps(overlap_summary, indent=1))
        for o in overlap:
            print(" ", o)

    return {"part2": {"a_task_pool": a, "b_c_alternative_suites": b},
            "part3_mbpp_cross_check": {"rows": p3, "summary": p3_summary},
            "supp_census_vs_calibration_same_artifacts": {"rows": overlap, "summary": overlap_summary}}


# ------------------------------------------------- Supplementary: HumanEval/15
def he15_transcript_check():
    """HumanEval/15 is passed by no census artifact. Read the archived census
    transcripts in memory (nothing is extracted) and count how many HumanEval/15
    generations contain the canonical construction (a join over range(n + 1)).
    This is a text heuristic, not an execution check."""
    import re
    import tarfile
    if not os.path.exists(CENSUS_TGZ):
        return {"available": False}
    pat = re.compile(r"range\(\s*(0\s*,\s*)?n\s*\+\s*1\s*\)")
    smoke = Counter()
    with tarfile.open(CENSUS_TGZ, "r:gz") as tf:
        for m in tf.getmembers():
            if not (m.isfile() and m.name.startswith("results/transcripts/")
                    and m.name.endswith(".jsonl") and not m.name.endswith(".full164.jsonl")):
                continue
            for line in tf.extractfile(m):
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("task_id") == "HumanEval/15":
                    sol = r.get("solution", "")
                    smoke["canonical_construction" if pat.search(sol) and "join" in sol else "other"] += 1
    scored = {}
    for name in ("results/audit_scored.jsonl", "results-mac/audit_scored.jsonl",
                 "results-metalrep/audit_scored.jsonl"):
        pth = os.path.join(P2, name)
        if os.path.exists(pth):
            rows = [json.loads(l) for l in open(pth) if l.strip()]
            rows = [r for r in rows if isinstance(r.get("per_task"), dict) and "HumanEval/15" in r["per_task"]]
            scored[name] = {"rows": len(rows), "he15_pass": sum(bool(r["per_task"]["HumanEval/15"]) for r in rows)}
    return {"available": True, "archive": CENSUS_TGZ, "archive_sha256": sha256(CENSUS_TGZ),
            "smoke_transcripts_he15_generations": dict(smoke),
            "scored_files_he15_pass_counts": scored}


# ------------------------------------------------------------ main
def main():
    tables = "--tables" in sys.argv
    suite = json.load(open(SUITE_FILE))["suite_tasks"]
    assert len(suite) == 15
    rows = [json.loads(l) for l in open(CENSUS) if l.strip()]
    official = [r for r in rows if r.get("channel") == "ollama-official"]
    assert len(official) == 305 and len({r["tag"] for r in official}) == 305
    for r in official:
        assert set(r["per_task"]) == set(suite)
    ns = load_analyze_helpers()

    try:
        import numpy  # noqa: F401
        have_numpy = True
    except ImportError:
        have_numpy = False

    p1 = part1(ns, suite, official, tables)
    p23 = part2_3(suite, official, tables)
    he15 = he15_transcript_check()
    if tables:
        print("\nHumanEval/15 check:", json.dumps(he15, indent=1))

    inputs = [CENSUS, SUITE_FILE, ANALYZE_PY, CLASSIFY_PY, FINDINGS]
    p1_files = sorted(glob.glob(os.path.join(P1_RES, "*.samples-sanitized_eval_results.json")))
    out = {
        "analysis": "A1 suite-size and task-choice sensitivity (existing data only, no model runs)",
        "meta": {
            "seed": SEED, "rng": "Python random.Random (Mersenne Twister). Independent instances, "
                                 "each seeded with SEED: (1) part 1 primary curve, k = 3..15 in "
                                 "order; (2) part 1 live-task variant, k = 3..14 in order; (3) part 2, "
                                 "39-pool draws then 164-pool draws",
            "n_draws": N_DRAWS,
            "sampling_part1": "for each k, all C(15,k) subsets if C(15,k) <= 1000, otherwise 1000 "
                              "distinct subsets sampled uniformly without replacement from all C(15,k)",
            "sampling_part2": "1000 suites of 15 tasks, each drawn uniformly without replacement "
                              "from the pool; suites drawn independently (duplicates counted)",
            "percentiles": "linear interpolation between order statistics (type 7)",
            "python": platform.python_version(), "numpy_available": have_numpy,
            "pass_definition_p1": "task passes iff base_status == plus_status == 'pass'",
            "scaling_rules": {
                "stage_one": "flag iff s < 0.6k (5s < 3k); k=15 gives s < 9",
                "healthy": "s / b >= 0.6 (unchanged ratio rule)",
                "defect_suspect": "15s <= 2k and 15b >= 8k (i.e. s <= 2k/15, b >= 8k/15; exact "
                                  "rationals, no rounding); k=15 gives s <= 2, b >= 8",
                "collapsed": "s / b < 0.6 and 15b < 8k",
                "degraded": "otherwise, with a baseline",
                "baseline": "median subset score of the artifact's model+size siblings whose tag "
                            "contains q6_K, q8_0, fp16 or f16 (analyze.py HIGH), official channel only",
                "grouping": "analyze.py size_key (norm_model, norm_size), executed from its source",
                "stage_two_scope": "applied to stage-one flagged artifacts; a suspect always has "
                                   "s <= 2k/15 < 0.6k so it is always flagged",
            },
            "confirmed_defects_4": CONFIRMED_4,
            "under_readjudication": PHI,
            "inputs_sha256": {p: sha256(p) for p in inputs},
            "p1_eval_files_sha256": {os.path.basename(p): sha256(p) for p in p1_files},
        },
        "part1_census_suite_size": p1,
        **p23,
        "supp_humaneval_15_dead_task_check": he15,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
