#!/usr/bin/env python3
"""A1 suite-size analysis (part 1) re-run on the CORRECTED census scores.

The released A1 (p2-v2-work/rerun-2026-10/a1/a1_analysis.py) read the per-task
results of results/audit_scored.jsonl, in which HumanEval/15 fails for all 305
official artifacts (50 stage-one flags at k = 15). This script takes the per-task
results for the 15 suite tasks from the executed rescore (census_rescore.jsonl,
134 artifacts gain HumanEval/15, 1 gains HumanEval/23) and recomputes the
suite-size curve against the corrected full-suite reference (43 flags, 7 suspects).

Reuse. a1_analysis.py is imported as a module (its main() is guarded, nothing
runs on import). Its constants and helpers are used unchanged: seed, popcount
table, jaccard, summ/pct, the generalized stage-one/stage-two rules
(stage_one_flag, stage_two), the analyze.py grouping helpers executed from
source (load_analyze_helpers), and part2_3 for the calibration check. The
suite-size curve is a closure inside a1_analysis.part1 and cannot be imported,
so it is transcribed below with two parameters added (enumeration cap and draw
count). The transcription is validated by reproducing every per-k metric of the
released a1_results.json from the original scores with the released settings
(enumerate <= 1000, 1000 draws).

Primary settings (this re-run): for each k = 3..15, all C(15,k) subsets when
C(15,k) <= 3003, otherwise 2000 distinct subsets drawn uniformly without
replacement; one random.Random(20261021) stream consumed in order of k.

Also re-runs a1_analysis.part2_3 (calibration data only) to confirm that the
"94% of random 15-of-164 suites flag a healthy calibration config" figure does
not depend on the census.

Run: python3 a1_rescored.py      (writes a1_rescored.json next to it)
Standard library only.
"""
import importlib.util
import itertools
import json
import os
import platform
import random
import statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# Paths are configurable; defaults follow the repository layout (rerun-2026-10/a1, rerun-2026-10/analysis).
RERUN = os.environ.get("QUANTCHECK_RERUN_DIR", os.path.abspath(os.path.join(HERE, "..")))
A1_DIR = os.environ.get("QUANTCHECK_A1_DIR", HERE)
A1_PY = os.path.join(A1_DIR, "a1_analysis.py")
A1_RESULTS = os.path.join(A1_DIR, "a1_results.json")
RESCORE = os.path.join(RERUN, "census_rescore.jsonl")
NUMBERS = os.environ.get("QUANTCHECK_NUMBERS_JSON", os.path.join(RERUN, "analysis", "numbers_v3.json"))
OUT_JSON = os.path.join(HERE, "a1_rescored.json")

spec = importlib.util.spec_from_file_location("a1_analysis", A1_PY)
A1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A1)

SEED = A1.SEED                  # 20261021
ENUM_MAX = 3003                 # enumerate all subsets when C(15,k) <= 3003
N_DRAWS = 2000                  # otherwise this many distinct seeded draws
LEGACY = {"enum_max": A1.N_DRAWS, "n_draws": A1.N_DRAWS}   # released A1 settings (1000/1000)

REBUILT_5 = A1.CONFIRMED_5      # 4 Qwen2.5-Coder 3B + phi3.5 q2_K
LLAMA = ["llama3.2:1b-instruct-q2_K", "llama3.2:1b-instruct-q3_K_S"]


# ---------------------------------------------------------------- data
def jnorm(x):
    return json.loads(json.dumps(x))


def load_official(suite, source):
    """305 official census rows; per_task / smoke_pass from the rescore if source == 'rescored'."""
    rows = [json.loads(l) for l in open(A1.CENSUS) if l.strip()]
    official = [r for r in rows if r.get("channel") == "ollama-official"]
    assert len(official) == 305 and len({r["tag"] for r in official}) == 305
    if source == "original":
        return official
    rs = [json.loads(l) for l in open(RESCORE) if l.strip()]
    assert len(rs) == 334 and len({r["tag"] for r in rs}) == 334
    by_tag = {r["tag"]: r for r in rs}
    out = []
    for r in official:
        x = by_tag[r["tag"]]
        stem = r["tag"].replace(":", "_")   # smoke transcript of artifacts that also have a full164 run: .smoke.jsonl
        assert x["transcript"] in (stem + ".jsonl", stem + ".smoke.jsonl"), (r["tag"], x["transcript"])
        assert set(x["per_task"]) == set(suite)
        pt = {t: bool(x["per_task"][t]) for t in suite}
        assert sum(pt.values()) == x["n_pass"]
        out.append(dict(r, per_task=pt, smoke_pass=x["n_pass"],
                        smoke_pass_original=r["smoke_pass"], per_task_original=r["per_task"]))
    return out


# ---------------------------------------------------------------- screen
def build(ns, suite, official):
    size_key, HIGH = ns["size_key"], ns["HIGH"]
    n = len(official)
    tags = [r["tag"] for r in official]
    masks = [sum(1 << j for j, t in enumerate(suite) if r["per_task"][t]) for r in official]
    gkey = [size_key(t) for t in tags]
    groups = defaultdict(list)
    for i in range(n):
        groups[gkey[i]].append(i)
    hp = {g: [i for i in m if any(h in tags[i] for h in HIGH)] for g, m in groups.items()}

    def screen(sub_mask, k):
        """a1_analysis.part1.screen, unchanged."""
        scores = [A1.POP[m & sub_mask] for m in masks]
        base = {g: (statistics.median([scores[i] for i in hp[g]]) if hp[g] else None) for g in groups}
        flagged = {i for i in range(n) if A1.stage_one_flag(scores[i], k)}
        cls = {i: A1.stage_two(scores[i], base[gkey[i]], k) for i in flagged}
        return scores, base, flagged, cls

    return {"n": n, "tags": tags, "masks": masks, "gkey": gkey, "groups": groups, "hp": hp, "screen": screen}


def curve(S_, suite, pool, flag15, susp15, rng, enum_max, n_draws, detail_k=None):
    """Transcription of a1_analysis.part1.curve with the enumeration cap and draw
    count as parameters; adds per-suspect drop-out rates for all 7 reference
    suspects and the per-k Jaccard summaries asked for in the re-run."""
    screen, tags = S_["screen"], S_["tags"]
    idx = {t: i for i, t in enumerate(tags)}
    c4 = {idx[t] for t in A1.CONFIRMED_4}
    c5 = {idx[t] for t in A1.CONFIRMED_5}
    per_k, detail = [], []
    for k in range(3, len(pool) + 1):
        combos = list(itertools.combinations(pool, k))
        enumerated = len(combos) <= enum_max
        subsets = combos if enumerated else rng.sample(combos, n_draws)
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
            jf.append(A1.jaccard(flg, flag15))
            rf.append(len(flg & flag15) / len(flag15))
            newf.append(len(flg - flag15))
            ns_.append(len(sus))
            js.append(A1.jaccard(sus, susp15))
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
        smin = -(-3 * k // 5)
        per_k.append({
            "k": k, "n_subsets": S, "n_possible": len(combos), "enumerated": enumerated,
            "stage_one_rule": f"flag iff s < {3 * k / 5:g}; unflagged needs s >= {smin} "
                              f"({100 * smin / k:.1f}% of k)",
            "effective_pass_fraction_to_stay_unflagged": round(smin / k, 4),
            "suspect_rule": f"s <= {2 * k / 15:.3f} and b >= {8 * k / 15:.3f}",
            "n_flags": A1.summ(nf, 2),
            "jaccard_flags_vs_full": A1.summ(jf, 3),
            "recall_of_full_suite_flags": A1.summ(rf, 3),
            "flags_not_in_full_set": A1.summ(newf, 2),
            "n_suspects": A1.summ(ns_, 2),
            "jaccard_suspects_vs_full": A1.summ(js, 3),
            "frac_suspect_set_identical_to_full": round(sum(exact) / S, 4),
            "frac_all_4_confirmed_are_suspects": round(sum(all4) / S, 4),
            "frac_all_5_confirmed_incl_phi35_are_suspects": round(sum(all5) / S, 4),
            "frac_all_5_confirmed_flagged_stage_one": round(flag_retain5 / S, 4),
            "per_defect_suspect_rate": {t: round(retain[t] / S, 4) for t in A1.CONFIRMED_5},
            "mean_suspects_not_in_full_set": round(statistics.fmean(extra_n), 3),
            "mean_full_suspects_lost": round(statistics.fmean(lost_n), 3),
            "mean_suspects_not_confirmed_4def": round(statistics.fmean(nonconf4), 3),
            "mean_suspects_not_confirmed_5def": round(statistics.fmean(nonconf5), 3),
            "top_extra_suspects": [[t, round(c / S, 4)] for t, c in extra_ctr.most_common(6)],
            "lost_full_suspects": [[t, round(c / S, 4)] for t, c in lost_ctr.most_common()],
            "mean_stage_two_classes_of_flagged": {c: round(v / S, 3) for c, v in sorted(cls_ctr.items())},
            # added in this re-run
            "suspect_dropout_rate": {tags[i]: round(lost_ctr[tags[i]] / S, 4) for i in sorted(susp15, key=lambda i: tags[i])},
            "suspect_dropout_count": {tags[i]: lost_ctr[tags[i]] for i in sorted(susp15, key=lambda i: tags[i])},
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
        "min_k_all5_retained_eq_1.00": first_k(lambda r: r["frac_all_5_confirmed_incl_phi35_are_suspects"] == 1.0),
        "min_k_suspect_set_identical_ge_0.95": first_k(lambda r: r["frac_suspect_set_identical_to_full"] >= 0.95),
        "note": "smallest k such that the criterion holds at that k and every larger k",
    }
    return per_k, detail, thresholds


def run(ns, suite, official, enum_max, n_draws, detail_k=14):
    S_ = build(ns, suite, official)
    _, base15, flag15, cls15 = S_["screen"]((1 << 15) - 1, 15)
    susp15 = {i for i, c in cls15.items() if c == "DEFECT_SUSPECT"}
    per_k, detail, thr = curve(S_, suite, list(range(15)), flag15, susp15,
                               random.Random(SEED), enum_max, n_draws, detail_k)
    return S_, base15, flag15, cls15, susp15, per_k, detail, thr


# ---------------------------------------------------------------- main
def main():
    suite = json.load(open(A1.SUITE_FILE))["suite_tasks"]
    assert len(suite) == 15
    ns = A1.load_analyze_helpers()
    released = json.load(open(A1_RESULTS))
    numbers = json.load(open(NUMBERS))

    # ---- 1. validate the transcription: original scores + released settings reproduce a1_results.json
    orig = load_official(suite, "original")
    _, _, oflag, _, osus, o_perk, o_det, o_thr = run(ns, suite, orig, **LEGACY)
    rel = released["part1_census_suite_size"]
    mismatches = []
    for mine, theirs in zip(o_perk, rel["per_k"]):
        for key, v in theirs.items():
            if mine.get(key) != v:
                mismatches.append((theirs["k"], key))
    validation = {
        "settings": "original audit_scored.jsonl per_task, enumerate if C(15,k) <= 1000 else 1000 draws, seed 20261021",
        "flags_k15": len(oflag), "suspects_k15": len(osus),
        "per_k_metrics_compared": sum(len(r) for r in rel["per_k"]),
        "per_k_mismatches": mismatches,
        "k14_leave_one_out_identical": o_det == rel["k14_leave_one_out"],
        "stability_thresholds_identical": all(o_thr[k] == v for k, v in rel["stability_thresholds"].items()),
    }
    validation["reproduces_released_a1_exactly"] = (not mismatches and validation["k14_leave_one_out_identical"]
                                                     and validation["stability_thresholds_identical"])
    assert validation["reproduces_released_a1_exactly"], validation

    # ---- 2. corrected scores, k = 15 reference
    resc = load_official(suite, "rescored")
    S_, base15, flag15, cls15, susp15, per_k, k14, thr = run(ns, suite, resc, ENUM_MAX, N_DRAWS)
    tags, gkey, n = S_["tags"], S_["gkey"], S_["n"]
    scores15 = [A1.POP[m] for m in S_["masks"]]
    rename = {"DEFECT_SUSPECT": "SUSPECT"}
    all_cls = Counter(rename.get(c, c) for c in
                      (A1.stage_two(scores15[i], base15[gkey[i]], 15) for i in range(n)))
    all_cls_literal = Counter(rename.get(c, c) for c in
                              (A1.analyze_py_literal(resc[i]["smoke_pass"], base15[gkey[i]]) for i in range(n)))
    live = [j for j in range(15) if any(m >> j & 1 for m in S_["masks"])]
    changed = [r for r in resc if r["smoke_pass"] != r["smoke_pass_original"]]
    flips = Counter(t for r in changed for t in suite if r["per_task"][t] != bool(r["per_task_original"][t]))
    orig_flag_tags = {orig[i]["tag"] for i in oflag}
    verification = {
        "smoke_pass_equals_rescore_n_pass": all(scores15[i] == resc[i]["smoke_pass"] for i in range(n)),
        "stage_one_flags_full_suite": len(flag15),
        "matches_numbers_v3_stage1_flags_rescored": len(flag15) == numbers["stage1_flags_rescored"],
        "suspects_full_suite": sorted(tags[i] for i in susp15),
        "matches_numbers_v3_suspects_rescored": sorted(tags[i] for i in susp15) == numbers["suspects_rescored"],
        "class_distribution_all_305": dict(all_cls),
        "class_distribution_literal_analyze_py": dict(all_cls_literal),
        "matches_numbers_v3_classes_rescored": dict(all_cls) == numbers["classes_rescored"] == dict(all_cls_literal),
        "artifacts_changed_by_rescore": len(changed),
        "task_flips_fail_to_pass": dict(flips),
        "any_pass_to_fail_flip": any(bool(r["per_task_original"][t]) and not r["per_task"][t] for r in resc for t in suite),
        "flags_original_not_rescored": sorted(orig_flag_tags - {tags[i] for i in flag15}),
        "flags_rescored_not_original": sorted({tags[i] for i in flag15} - orig_flag_tags),
        "tasks_passed_by_no_artifact": [suite[j] for j in range(15) if j not in live],
        "rebuilt_5_full_suite_scores": {t: scores15[tags.index(t)] for t in REBUILT_5},
        "llama_full_suite_scores_and_baselines": {t: {"s": scores15[tags.index(t)], "b": base15[gkey[tags.index(t)]]}
                                                  for t in LLAMA},
    }
    assert verification["smoke_pass_equals_rescore_n_pass"]
    assert len(flag15) == 43 and len(susp15) == 7
    assert verification["matches_numbers_v3_stage1_flags_rescored"]
    assert verification["matches_numbers_v3_suspects_rescored"]
    assert verification["matches_numbers_v3_classes_rescored"]
    assert set(REBUILT_5) | set(LLAMA) == {tags[i] for i in susp15}

    # ---- 3. corrected scores with the released settings (cross-check against the gate re-implementations)
    _, _, _, _, _, l_perk, _, _ = run(ns, suite, resc, **LEGACY)
    legacy_rescored = [{"k": r["k"], "n_subsets": r["n_subsets"],
                        "mean_jaccard_flags": r["jaccard_flags_vs_full"]["mean"],
                        "mean_jaccard_suspects": r["jaccard_suspects_vs_full"]["mean"],
                        "frac_all_5_rebuilt_suspects": r["frac_all_5_confirmed_incl_phi35_are_suspects"],
                        "dropout_rate": r["suspect_dropout_rate"]} for r in l_perk]

    # ---- 4. calibration (part 2/3): rerun a1_analysis.part2_3, compare with released
    p23 = A1.part2_3(suite, resc, False)
    p1_files = sorted(os.path.basename(p) for p in
                      __import__("glob").glob(os.path.join(A1.P1_RES, "*.samples-sanitized_eval_results.json")))
    p1_hashes_same = all(A1.sha256(os.path.join(A1.P1_RES, f)) == released["meta"]["p1_eval_files_sha256"].get(f)
                         for f in p1_files) and len(p1_files) == len(released["meta"]["p1_eval_files_sha256"])
    pb = p23["part2"]["b_c_alternative_suites"]["pool164"]
    calib = {
        "figure": "share of 1000 random 15-of-164 HumanEval+ suites in which the 60% bar flags >= 1 healthy "
                  "calibration config (P1 data, 23 healthy Qwen2.5-Coder configs)",
        "census_used": False,
        "frac_suites_flagging_ge1_healthy": pb["frac_suites_flagging_ge1_healthy"],
        "wilson95": pb["frac_suites_flagging_ge1_healthy_wilson95"],
        # compare after a JSON round trip (int dict keys become strings in the released file)
        "part2_identical_to_released": jnorm(p23["part2"]) == released["part2"],
        "part3_mbpp_identical_to_released": jnorm(p23["part3_mbpp_cross_check"]) == released["part3_mbpp_cross_check"],
        "p1_eval_files_sha256_unchanged": p1_hashes_same,
        "census_vs_calibration_overlap_summary_corrected": p23["supp_census_vs_calibration_same_artifacts"]["summary"],
        "census_vs_calibration_overlap_summary_released": released["supp_census_vs_calibration_same_artifacts"]["summary"],
        "note": "part2 reads only the P1 calibration eval files and its own RNG; the census rows are passed to "
                "part2_3 only for the supplementary census-vs-calibration overlap, which does change",
    }
    assert calib["part2_identical_to_released"] and calib["p1_eval_files_sha256_unchanged"]

    # ---- phi3.5 q2_K drop-outs (k = 3, 4 are fully enumerated): which subsets, and why
    iphi = tags.index(A1.PHI)
    phi_drops = []
    for k in (3, 4):
        for sub in itertools.combinations(range(15), k):
            _, base, _, cls = S_["screen"](sum(1 << j for j in sub), k)
            if cls.get(iphi) != "DEFECT_SUSPECT":
                phi_drops.append({"k": k, "tasks": [suite[j] for j in sub], "class": cls.get(iphi),
                                  "s": 0, "b": base[gkey[iphi]], "cap_b": 8 * k / 15})
    hp_phi = {tags[j]: [suite[t] for t in range(15) if not S_["masks"][j] >> t & 1] for j in S_["hp"][gkey[iphi]]}

    # ---- summary ranges for the text
    def rng_of(key, ks):
        v = [r["suspect_dropout_rate"][key] for r in per_k if r["k"] in ks]
        return [min(v), max(v)]
    nz = lambda t: [r["k"] for r in per_k if r["suspect_dropout_rate"][t] > 0]
    by_k = {r["k"]: r for r in per_k}
    headline = {
        "mean_jaccard_flags": {k: by_k[k]["jaccard_flags_vs_full"]["mean"] for k in range(3, 16)},
        "mean_jaccard_suspects": {k: by_k[k]["jaccard_suspects_vs_full"]["mean"] for k in range(3, 16)},
        "frac_all_5_rebuilt_suspects": {k: by_k[k]["frac_all_5_confirmed_incl_phi35_are_suspects"] for k in range(3, 16)},
        "min_k_all_5_rebuilt_kept_in_every_subset_from_then_on": thr["min_k_all5_retained_eq_1.00"],
        "phi35_q2K_dropout_by_k": {r["k"]: r["suspect_dropout_rate"][A1.PHI] for r in per_k if r["suspect_dropout_rate"][A1.PHI] > 0},
        "llama_q3_K_S_dropout_range_k3_14": rng_of(LLAMA[1], range(3, 15)),
        "llama_q3_K_S_dropout_nonzero_k": nz(LLAMA[1]),
        "llama_q2_K_dropout_max": max(r["suspect_dropout_rate"][LLAMA[0]] for r in per_k),
        "llama_q2_K_dropout_nonzero_k": nz(LLAMA[0]),
    }

    out = {
        "analysis": "A1 part 1 (census suite-size curve) on corrected census scores (census_rescore.jsonl)",
        "meta": {
            "seed": SEED, "enum_max": ENUM_MAX, "n_draws": N_DRAWS,
            "sampling": "for each k = 3..15: all C(15,k) subsets if C(15,k) <= 3003 (k = 3,4,5,10..15), otherwise "
                        "2000 distinct subsets drawn uniformly without replacement (k = 6..9); one "
                        "random.Random(20261021) instance consumed in order of k",
            "rules": "a1_analysis.stage_one_flag / stage_two (scaled: flag s < 0.6k; suspect 15s <= 2k and 15b >= 8k; "
                     "healthy s/b >= 0.6), analyze.py grouping and HIGH baseline siblings",
            "per_task_source": "census_rescore.jsonl per_task for the 15 suite tasks, 305 ollama-official tags; "
                               "all other row fields from results/audit_scored.jsonl",
            "reference": "full 15-task suite on corrected scores: 43 flags, 7 suspects",
            "rebuilt_5": REBUILT_5, "llama_suspects": LLAMA,
            "reused_from": A1_PY,
            "python": platform.python_version(),
            "inputs_sha256": {p: A1.sha256(p) for p in (A1_PY, A1.CENSUS, RESCORE, A1.SUITE_FILE, A1.ANALYZE_PY, NUMBERS)},
        },
        "validation_reproduces_released_a1": validation,
        "verification_k15_corrected": verification,
        "full_suite_reference": {"flags": sorted(tags[i] for i in flag15),
                                 "suspects": sorted(tags[i] for i in susp15),
                                 "stage_two_classes_of_flagged": dict(Counter(cls15.values()))},
        "headline": headline,
        "per_k": per_k,
        "k14_leave_one_out": k14,
        "phi35_q2K_dropouts": {"subsets": phi_drops, "high_precision_siblings_failed_tasks": hp_phi,
                               "note": "phi3.5 q2_K scores 0; it leaves the suspect class only when the median of its "
                                       "q6_K/q8_0/fp16 siblings on the subset falls below 8k/15"},
        "stability_thresholds": thr,
        "cross_check_corrected_with_released_settings_1000": legacy_rescored,
        "calibration_94pct_check": calib,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1)

    # ---- compact summary
    print(f"validation: released A1 reproduced exactly from original scores: {validation['reproduces_released_a1_exactly']}"
          f" ({validation['per_k_metrics_compared']} per-k values, k14 LOO, thresholds)")
    print(f"corrected k=15: flags {len(flag15)} (original 50; left: {len(verification['flags_original_not_rescored'])}, "
          f"new: {len(verification['flags_rescored_not_original'])}), suspects {len(susp15)}, classes {dict(all_cls)}, "
          f"dead tasks {verification['tasks_passed_by_no_artifact']}")
    print(f"settings: enumerate if C(15,k)<=3003 else {N_DRAWS} draws, seed {SEED}")
    print("k  subsets   J_flags  J_susp  all5   llama_q2_K  llama_q3_K_S  phi35_q2_K")
    for r in per_k:
        d = r["suspect_dropout_rate"]
        print(f"{r['k']:<2} {r['n_subsets']:>5}{'*' if r['enumerated'] else ' '}   {r['jaccard_flags_vs_full']['mean']:.3f}    "
              f"{r['jaccard_suspects_vs_full']['mean']:.3f}   {r['frac_all_5_confirmed_incl_phi35_are_suspects']:.4f} "
              f"{d[LLAMA[0]]:.4f}      {d[LLAMA[1]]:.4f}        {d[A1.PHI]:.4f}")
    print("headline:", json.dumps({k: v for k, v in headline.items()
                                   if k not in ("mean_jaccard_flags", "mean_jaccard_suspects", "frac_all_5_rebuilt_suspects")}))
    print("cross-check (released 1000-draw settings, corrected scores): J_flags k5 %.3f k10 %.3f"
          % (legacy_rescored[2]["mean_jaccard_flags"], legacy_rescored[7]["mean_jaccard_flags"]))
    print(f"calibration 94% figure: {calib['frac_suites_flagging_ge1_healthy']} {calib['wilson95']}, "
          f"part2 identical to released: {calib['part2_identical_to_released']}, P1 hashes unchanged: "
          f"{calib['p1_eval_files_sha256_unchanged']}")
    print("census-vs-calibration overlap (corrected):", json.dumps(calib["census_vs_calibration_overlap_summary_corrected"]))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
