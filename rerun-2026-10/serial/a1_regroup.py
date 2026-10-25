#!/usr/bin/env python3
"""A1 suite-size analysis on SERIAL scores with CHECKPOINT-IDENTITY baselines (regroup copy of a1_serial.py).

Only three things differ from a1_serial.py (same folder):
  1. Grouping. The stage-two baseline group of a tag is its checkpoint identity, the full registry tag
     minus its quantization suffix (ckpt_key; = census heatmap column key, as in numbers_regroup.py),
     instead of analyze.py size_key = (norm_model, norm_size), which pools aliases. The transcription
     check against the released a1_results.json still runs with size_key, because that file was made
     with it; every serial analysis uses the checkpoint grouping. The result is also compared, per k and
     per metric, with a1_serial.json (same scores and settings, size_key grouping).
  2. Paths. Every input path follows the repository layout (this file is rerun-2026-10/serial/) and can
     be overridden by an environment variable: QUANTCHECK_ROOT, QUANTCHECK_SERIAL_DIR,
     QUANTCHECK_A1_DIR, QUANTCHECK_P1_RESULTS, QUANTCHECK_TUNING_DIR, QUANTCHECK_OUT_DIR (the QC_* names
     of the author's working copy are accepted as aliases). a1_analysis.py is imported and its input
     paths are re-pointed at the same files (module globals P2, CENSUS, SUITE_FILE, ANALYZE_PY,
     CLASSIFY_PY, FINDINGS, P1_RES, CENSUS_TGZ). Paths written to the output JSON are relative to this
     script, except the two tuning files and numbers_regroup.json, which are written under their bare
     names wherever they are read from; a tuning file that is absent is written as
     "<withheld tuning data>/<file name>".
  3. Tuning inputs. The calibration check (part 4 below: the "94% of random 15-of-164 suites" figure
     and the MBPP+ cross-check) reads the serially re-scored per-task results of the 24 screen-tuning
     configurations, tuning_p1_*_serial.jsonl (QUANTCHECK_TUNING_DIR; released in this directory since
     v3.3). Each row carries the tasks whose verdict changed against the pool-scored evaluation
     ("flips"), so the serial-versus-pool differences are recomputed from the released files alone. The
     original EvalPlus result files of the tuning study (QUANTCHECK_P1_RESULTS) are not released; when
     they are present the script also checks them against the hashes in the released a1_results.json
     and against the flips. Without the serial files, parts 1 to 3 and the drop-out analyses are
     recomputed, and calibration_94pct_check, headline.calibration_94pct and the two tuning-file hashes
     are copied from the committed a1_regroup.json; calibration_94pct_check is then marked
     from_committed_file.
Reads numbers_regroup.json from QUANTCHECK_OUT_DIR (run numbers_regroup.py first with the same setting);
writes a1_regroup.json there (default: next to this script).

Original docstring of a1_serial.py follows.

A1 suite-size analysis (part 1) re-run on the SERIAL census scores, every subset enumerated.

Copy of ../a1_rescored.py with three changes:
  1. Per-task results for the 15 suite tasks come from the serial re-scoring
     (census_smoke_serial.jsonl: one evaluation at a time, default EvalPlus time limits)
     instead of the pool-scored census_rescore.jsonl. Against the original census
     (results/audit_scored.jsonl) 275 official artifacts gain HumanEval/15 and one of
     them also HumanEval/23; the full-suite reference becomes 39 flags, 7 suspects.
  2. ENUM_MAX = 6435 = max_k C(15,k), so for every k = 3..15 ALL C(15,k) subsets are
     enumerated (32,647 subsets in total) and every per-k value is exact; the seeded
     random stream is never consumed.
  3. The calibration check (a1_analysis.part2_3) reads the serially re-scored paper-1
     tuning configurations (tuning_p1_humaneval_serial.jsonl, tuning_p1_mbpp_serial.jsonl)
     through a replacement for a1_analysis.load_p1 with the same return shape.

Everything else is unchanged: a1_analysis.py is imported as a module and its constants and
helpers are used as they are (seed, popcount table, jaccard, summ/pct, stage_one_flag,
stage_two, load_analyze_helpers, part2_3). The transcription of a1_analysis.part1.curve is
validated, as in a1_rescored.py, by reproducing every per-k metric of the released
a1_results.json from the original scores with the released settings (enumerate <= 1000,
1000 draws).

Run: python3 -I a1_serial.py      (writes a1_serial.json next to it; this copy: a1_regroup.py -> a1_regroup.json)
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
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))                 # rerun-2026-10/serial


ENV_ALIASES = {"QUANTCHECK_ROOT": "QC_P2_ROOT", "QUANTCHECK_SERIAL_DIR": "QC_SERIAL_DIR",
               "QUANTCHECK_A1_DIR": "QC_A1_DIR", "QUANTCHECK_P1_RESULTS": "QC_P1_RES",
               "QUANTCHECK_OUT_DIR": "QC_OUT_DIR"}   # QC_*: names used in the author's working copy


def _dir(var, default):
    """input/output folder: the environment variable (or its QC_* alias) if set, else a path
    relative to this script"""
    return os.path.abspath(os.environ.get(var) or os.environ.get(ENV_ALIASES.get(var, ""), "") or default)


P2 = _dir("QUANTCHECK_ROOT", os.path.join(HERE, "..", ".."))                          # repository root
SER = _dir("QUANTCHECK_SERIAL_DIR", HERE)
A1_DIR = _dir("QUANTCHECK_A1_DIR", os.path.join(HERE, "..", "a1"))
P1_RES = _dir("QUANTCHECK_P1_RESULTS", os.path.join(P2, "p1_results"))               # original EvalPlus files: not in this release
TUNING_DIR = _dir("QUANTCHECK_TUNING_DIR", SER)                                        # tuning_p1_*_serial.jsonl: released here since v3.3
OUT_DIR = _dir("QUANTCHECK_OUT_DIR", HERE)
A1_PY = os.path.join(A1_DIR, "a1_analysis.py")
A1_RESULTS = os.path.join(A1_DIR, "a1_results.json")
RESCORE = os.path.join(SER, "census_smoke_serial.jsonl")           # serial census scores
TUNING_HE = os.path.join(TUNING_DIR, "tuning_p1_humaneval_serial.jsonl")   # serial paper-1 tuning configs
TUNING_MBPP = os.path.join(TUNING_DIR, "tuning_p1_mbpp_serial.jsonl")
NUMBERS = os.path.join(OUT_DIR, "numbers_regroup.json")             # regroup numbers (checkpoint grouping)
A1_POD = os.path.join(A1_DIR, "a1_rescored.json")                  # pod-rescore A1, comparison only
A1_SERIAL = os.path.join(SER, "a1_serial.json")                    # serial A1, size_key grouping, comparison only
A1_COMMITTED = os.path.join(SER, "a1_regroup.json")                # committed output (fallback when the tuning files are absent)
OUT_JSON = os.path.join(OUT_DIR, "a1_regroup.json")
WITHHELD = (TUNING_HE, TUNING_MBPP)

spec = importlib.util.spec_from_file_location("a1_analysis", A1_PY)
A1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A1)
# re-point the released module's hard-coded input paths at the same files, relative to this script
A1.P2 = P2
A1.CENSUS = os.path.join(P2, "results", "audit_scored.jsonl")
A1.SUITE_FILE = os.path.join(P2, "smoke_suite_v1.json")
A1.ANALYZE_PY = os.path.join(P2, "analysis", "analyze.py")
A1.CLASSIFY_PY = os.path.join(P2, "analysis", "classify.py")
A1.FINDINGS = os.path.join(P2, "analysis", "findings.json")
A1.P1_RES = P1_RES
A1.CENSUS_TGZ = os.path.join(P2, "results", "audit_data_full.tgz")
A1.OUT_JSON = None                                                  # never written from here


def relpath_out(p):
    if p in WITHHELD:      # tuning files: base name wherever they are read from, or a fixed label when absent
        return os.path.basename(p) if os.path.exists(p) else "<withheld tuning data>/" + os.path.basename(p)
    if p == NUMBERS:       # numbers_regroup.json: base name wherever QUANTCHECK_OUT_DIR points
        return os.path.basename(p)
    return os.path.relpath(p, HERE)


def input_sha256(p):
    """sha256 of an input; for a tuning file that is absent, the hash recorded in the committed output"""
    if os.path.exists(p) or p not in WITHHELD:
        return A1.sha256(p)
    d = json.load(open(A1_COMMITTED))["meta"]["inputs_sha256"]
    return d.get(os.path.basename(p)) or d["<withheld tuning data>/" + os.path.basename(p)]


def calibration_inputs_available():
    """True when both serial tuning files of the calibration check are present."""
    return all(os.path.exists(p) for p in WITHHELD)


def p1_originals_available():
    """True when the original (pool-scored) EvalPlus result files of the tuning study are present."""
    import glob
    return bool(glob.glob(os.path.join(P1_RES, "*.samples-sanitized_eval_results.json")))


QSUFFIX = sorted(["q2_K", "q3_K_S", "q3_K_M", "q3_K_L", "q4_0", "q4_K_S", "q4_K_M", "q5_0", "q5_K_S", "q5_K_M",
                  "q6_K", "q8_0", "fp16"], key=len, reverse=True)


def ckpt_key(tag):
    """checkpoint identity: full registry tag minus its quantization suffix (census heatmap column key)"""
    q = next(q for q in QSUFFIX if tag.endswith("-" + q))
    return tag[: -len(q) - 1]


GROUP = ckpt_key

SEED = A1.SEED                  # 20261021
ENUM_MAX = max(comb(15, k) for k in range(16))   # 6435: every subset at every k is enumerated
N_DRAWS = 2000                  # unused at this cap (kept for the call signature)
LEGACY = {"enum_max": A1.N_DRAWS, "n_draws": A1.N_DRAWS}   # released A1 settings (1000/1000)
assert ENUM_MAX == 6435

REBUILT_5 = A1.CONFIRMED_5      # 4 Qwen2.5-Coder 3B + phi3.5 q2_K
LLAMA = ["llama3.2:1b-instruct-q2_K", "llama3.2:1b-instruct-q3_K_S"]


# ---------------------------------------------------------------- data
def jnorm(x):
    return json.loads(json.dumps(x))


def load_official(suite, source):
    """305 official census rows; per_task / smoke_pass from the serial scores if source == 'serial'."""
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
        assert os.path.basename(x["transcript"]) in (stem + ".jsonl", stem + ".smoke.jsonl"), (r["tag"], x["transcript"])
        assert set(x["per_task"]) == set(suite)
        pt = {t: bool(x["per_task"][t]) for t in suite}
        assert sum(pt.values()) == x["n_pass"]
        assert x["old_n_pass_census_original"] == r["smoke_pass"]
        out.append(dict(r, per_task=pt, smoke_pass=x["n_pass"],
                        smoke_pass_original=r["smoke_pass"], per_task_original=r["per_task"],
                        smoke_pass_pod=x["old_n_pass"]))
    return out


def load_p1_serial(kind):
    """Replacement for a1_analysis.load_p1: {config stem: {task_id: passed}} from the serial files."""
    path = {"humaneval": TUNING_HE, "mbpp": TUNING_MBPP}[kind]
    out = {}
    for l in open(path):
        if l.strip():
            r = json.loads(l)
            out[r["id"]] = {t: bool(v) for t, v in r["per_task"].items()}
    return out


def load_p1_pool_from_flips(kind):
    """The pool-scored verdicts, reconstructed from each serial row's per_task and flips: a task listed in
    flips had the opposite verdict under the pool-scored evaluation."""
    path = {"humaneval": TUNING_HE, "mbpp": TUNING_MBPP}[kind]
    out = {}
    for l in open(path):
        if l.strip():
            r = json.loads(l)
            flips = {f if isinstance(f, str) else (f.get("task") or f.get("task_id")) for f in r["flips"]}
            assert all(flips), (r["id"], kind, r["flips"][:1])
            out[r["id"]] = {t: (not bool(v)) if t in flips else bool(v) for t, v in r["per_task"].items()}
            assert sum(out[r["id"]].values()) == r["old_n_pass"], (r["id"], kind)
    return out


# ---------------------------------------------------------------- screen
def build(ns, suite, official, key=None):
    key, HIGH = key or GROUP, ns["HIGH"]
    n = len(official)
    tags = [r["tag"] for r in official]
    assert all(ckpt_key(r["tag"]) == r["tag"][: -len(r["quant"]) - 1] for r in official)
    masks = [sum(1 << j for j, t in enumerate(suite) if r["per_task"][t]) for r in official]
    gkey = [key(t) for t in tags]
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
            # added in the re-run
            "suspect_dropout_rate": {tags[i]: round(lost_ctr[tags[i]] / S, 4) for i in sorted(susp15, key=lambda i: tags[i])},
            "suspect_dropout_count": {tags[i]: lost_ctr[tags[i]] for i in sorted(susp15, key=lambda i: tags[i])},
            # added in the serial run: exact counts behind the fractions
            "count_all_5_rebuilt_suspects": sum(all5),
            "mean_jaccard_flags_unrounded": statistics.fmean(jf),
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


def run(ns, suite, official, enum_max, n_draws, detail_k=14, key=None):
    S_ = build(ns, suite, official, key)
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
    pod_a1 = json.load(open(A1_POD))

    # ---- 1. validate the transcription: original scores + released settings reproduce a1_results.json
    orig = load_official(suite, "original")
    # transcription check: the released file was made with analyze.py size_key, so this check uses it
    _, _, oflag, _, osus, o_perk, o_det, o_thr = run(ns, suite, orig, key=ns["size_key"], **LEGACY)
    rel = released["part1_census_suite_size"]
    mismatches = []
    for mine, theirs in zip(o_perk, rel["per_k"]):
        for key, v in theirs.items():
            if mine.get(key) != v:
                mismatches.append((theirs["k"], key))
    validation = {
        "settings": "original audit_scored.jsonl per_task, enumerate if C(15,k) <= 1000 else 1000 draws, seed 20261021, "
                    "analyze.py size_key grouping (as released)",
        "flags_k15": len(oflag), "suspects_k15": len(osus),
        "per_k_metrics_compared": sum(len(r) for r in rel["per_k"]),
        "per_k_mismatches": mismatches,
        "k14_leave_one_out_identical": o_det == rel["k14_leave_one_out"],
        "stability_thresholds_identical": all(o_thr[k] == v for k, v in rel["stability_thresholds"].items()),
    }
    validation["reproduces_released_a1_exactly"] = (not mismatches and validation["k14_leave_one_out_identical"]
                                                     and validation["stability_thresholds_identical"])
    assert validation["reproduces_released_a1_exactly"], validation

    # ---- 2. serial scores, k = 15 reference, every subset enumerated
    resc = load_official(suite, "serial")
    S_, base15, flag15, cls15, susp15, per_k, k14, thr = run(ns, suite, resc, ENUM_MAX, N_DRAWS)
    assert all(r["enumerated"] and r["n_subsets"] == comb(15, r["k"]) for r in per_k)
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
    pod_flag_tags = {r["tag"] for r in resc if r["smoke_pass_pod"] < 9}
    verification = {
        "smoke_pass_equals_serial_n_pass": all(scores15[i] == resc[i]["smoke_pass"] for i in range(n)),
        "stage_one_flags_full_suite": len(flag15),
        "matches_numbers_regroup_stage1_flags": len(flag15) == numbers["stage1_flags_rescored"],
        "suspects_full_suite": sorted(tags[i] for i in susp15),
        "matches_numbers_regroup_suspects": sorted(tags[i] for i in susp15) == numbers["suspects_rescored"],
        "class_distribution_all_305": dict(all_cls),
        "class_distribution_literal_analyze_py": dict(all_cls_literal),
        "matches_numbers_regroup_classes": dict(all_cls) == numbers["classes_rescored"] == dict(all_cls_literal),
        "artifacts_changed_vs_original_census": len(changed),
        "task_flips_fail_to_pass_vs_original": dict(flips),
        "any_pass_to_fail_flip_vs_original": any(bool(r["per_task_original"][t]) and not r["per_task"][t] for r in resc for t in suite),
        "flags_original_not_serial": sorted(orig_flag_tags - {tags[i] for i in flag15}),
        "flags_serial_not_original": sorted({tags[i] for i in flag15} - orig_flag_tags),
        "flags_pod_rescore_not_serial": sorted(pod_flag_tags - {tags[i] for i in flag15}),
        "flags_serial_not_pod_rescore": sorted({tags[i] for i in flag15} - pod_flag_tags),
        "tasks_passed_by_no_artifact": [suite[j] for j in range(15) if j not in live],
        "rebuilt_5_full_suite_scores": {t: scores15[tags.index(t)] for t in REBUILT_5},
        "llama_full_suite_scores_and_baselines": {t: {"s": scores15[tags.index(t)], "b": base15[gkey[tags.index(t)]]}
                                                  for t in LLAMA},
    }
    assert verification["smoke_pass_equals_serial_n_pass"]
    assert len(flag15) == 39 and len(susp15) == 7
    assert verification["matches_numbers_regroup_stage1_flags"]
    assert verification["matches_numbers_regroup_suspects"]
    assert verification["matches_numbers_regroup_classes"]
    assert set(REBUILT_5) | set(LLAMA) == {tags[i] for i in susp15}

    # ---- 3. serial scores with the released settings (cross-check, 1000 draws at k = 5..10)
    _, _, _, _, _, l_perk, _, _ = run(ns, suite, resc, **LEGACY)
    legacy_serial = [{"k": r["k"], "n_subsets": r["n_subsets"], "enumerated": r["enumerated"],
                      "mean_jaccard_flags": r["jaccard_flags_vs_full"]["mean"],
                      "mean_jaccard_suspects": r["jaccard_suspects_vs_full"]["mean"],
                      "frac_all_5_rebuilt_suspects": r["frac_all_5_confirmed_incl_phi35_are_suspects"],
                      "dropout_rate": r["suspect_dropout_rate"]} for r in l_perk]

    # ---- 4. calibration (part 2/3) on the serial tuning configurations, compared with the released file
    if calibration_inputs_available():
        released_load_p1 = A1.load_p1
        ser_he, ser_mb = load_p1_serial("humaneval"), load_p1_serial("mbpp")
        pool_he, pool_mb = load_p1_pool_from_flips("humaneval"), load_p1_pool_from_flips("mbpp")
        if p1_originals_available():      # the original files, when present, must agree with the flips
            orig_he, orig_mb = released_load_p1("humaneval"), released_load_p1("mbpp")
            assert orig_he == pool_he and orig_mb == pool_mb, "original EvalPlus files disagree with the serial files' flips"
        assert sorted(ser_he) == sorted(pool_he) and sorted(ser_mb) == sorted(pool_mb)
        he_diff = {c: sorted(t for t in ser_he[c] if ser_he[c][t] != pool_he[c][t]) for c in ser_he}
        mb_diff = {c: sorted(t for t in ser_mb[c] if ser_mb[c][t] != pool_mb[c][t]) for c in ser_mb}
        A1.load_p1 = load_p1_serial
        try:
            p23 = A1.part2_3(suite, resc, False)
        finally:
            A1.load_p1 = released_load_p1
        if p1_originals_available():
            p1_files = sorted(os.path.basename(p) for p in
                              __import__("glob").glob(os.path.join(A1.P1_RES, "*.samples-sanitized_eval_results.json")))
            p1_hashes_same = all(A1.sha256(os.path.join(A1.P1_RES, f)) == released["meta"]["p1_eval_files_sha256"].get(f)
                                 for f in p1_files) and len(p1_files) == len(released["meta"]["p1_eval_files_sha256"])
        else:
            p1_hashes_same = "not checked: the original EvalPlus result files are not in this release"
        pb = p23["part2"]["b_c_alternative_suites"]["pool164"]
        p3s = p23["part3_mbpp_cross_check"]["summary"]
        rel3 = released["part3_mbpp_cross_check"]["summary"]
        calib = {
            "figure": "share of 1000 random 15-of-164 HumanEval+ suites in which the 60% bar flags >= 1 healthy "
                      "calibration config (serial P1 tuning data, 23 healthy Qwen2.5-Coder configs)",
            "census_used": False,
            "tuning_source": [relpath_out(TUNING_HE), relpath_out(TUNING_MBPP)],
            "humaneval_per_task_differences_serial_vs_pool": {c: v for c, v in he_diff.items() if v},
            "mbpp_per_task_differences_serial_vs_pool": {c: v for c, v in mb_diff.items() if v},
            "frac_suites_flagging_ge1_healthy": pb["frac_suites_flagging_ge1_healthy"],
            "wilson95": pb["frac_suites_flagging_ge1_healthy_wilson95"],
            "frac_suites_flagging_ge1_healthy_released": released["part2"]["b_c_alternative_suites"]["pool164"]["frac_suites_flagging_ge1_healthy"],
            # compare after a JSON round trip (int dict keys become strings in the released file)
            "part2_identical_to_released": jnorm(p23["part2"]) == released["part2"],
            "part3_mbpp_identical_to_released": jnorm(p23["part3_mbpp_cross_check"]) == released["part3_mbpp_cross_check"],
            "part3_mbpp_summary_serial": p3s,
            "part3_mbpp_summary_released": rel3,
            "mbpp_healthy_rate_range_pct_serial": [round(100 * p3s["healthy_mbpp_plus_rate"]["min"], 1),
                                                   round(100 * p3s["healthy_mbpp_plus_rate"]["max"], 1)],
            "mbpp_healthy_rate_range_pct_released": [round(100 * rel3["healthy_mbpp_plus_rate"]["min"], 1),
                                                     round(100 * rel3["healthy_mbpp_plus_rate"]["max"], 1)],
            "mbpp_defective_serial": p3s["defective_mbpp_plus"]["mbpp_plus_pass"],
            "pool39_and_suite": {k: p23["part2"]["a_task_pool"][k] for k in
                                 ("n_tasks_solved_by_all_healthy", "suite_equals_first_15_lexicographic",
                                  "all_healthy_15_of_15", "defective_suite_score")},
            "p1_eval_files_sha256_unchanged": p1_hashes_same,
            "census_vs_calibration_overlap_summary_serial": p23["supp_census_vs_calibration_same_artifacts"]["summary"],
            "census_vs_calibration_overlap_summary_released": released["supp_census_vs_calibration_same_artifacts"]["summary"],
            "note": "part2 reads only the tuning HumanEval+ results and its own RNG; the census rows are passed to "
                    "part2_3 only for the supplementary census-vs-calibration overlap, which does change",
        }
        assert calib["part2_identical_to_released"]
        assert calib["p1_eval_files_sha256_unchanged"] in (True, "not checked: the original EvalPlus result files are not in this release")
    else:  # tuning files absent: copy the committed values, marked as such
        calib = dict(json.load(open(A1_COMMITTED))["calibration_94pct_check"], from_committed_file=True)

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

    # ---- why the llama3.2-1B suspects drop out (every subset, k = 3..14)
    llama_reasons = {}
    for t in LLAMA:
        it = tags.index(t)
        per = {}
        for k in range(3, 15):
            c = Counter()
            for sub in itertools.combinations(range(15), k):
                sc, base, flg, cls = S_["screen"](sum(1 << j for j in sub), k)
                if cls.get(it) == "DEFECT_SUSPECT":
                    continue
                s, b = sc[it], base[gkey[it]]
                over_cap = 15 * s > 2 * k
                low_base = 15 * b < 8 * k
                c["score_above_cap_2k/15" if over_cap and not low_base else
                  "baseline_below_8k/15" if low_base and not over_cap else
                  "both" if over_cap and low_base else "other:" + str(cls.get(it))] += 1
            per[k] = dict(c)
        tot = Counter()
        for v in per.values():
            tot.update(v)
        llama_reasons[t] = {"by_k": per, "total": dict(tot),
                            "share_score_above_cap": round((tot["score_above_cap_2k/15"] + tot["both"]) / sum(tot.values()), 4)
                            if tot else None}

    # ---- summary ranges for the text
    def rng_of(key, ks):
        v = [r["suspect_dropout_rate"][key] for r in per_k if r["k"] in ks]
        return [min(v), max(v)]
    nz = lambda t: [r["k"] for r in per_k if r["suspect_dropout_rate"][t] > 0]
    by_k = {r["k"]: r for r in per_k}
    llama_q3 = {r["k"]: r["suspect_dropout_rate"][LLAMA[1]] for r in per_k}
    llama_q2 = {r["k"]: r["suspect_dropout_rate"][LLAMA[0]] for r in per_k}
    full5 = [k for k in range(3, 16) if by_k[k]["frac_all_5_confirmed_incl_phi35_are_suspects"] == 1.0]
    headline = {
        "mean_jaccard_flags": {k: by_k[k]["jaccard_flags_vs_full"]["mean"] for k in range(3, 16)},
        "mean_jaccard_suspects": {k: by_k[k]["jaccard_suspects_vs_full"]["mean"] for k in range(3, 16)},
        "frac_all_5_rebuilt_suspects": {k: by_k[k]["frac_all_5_confirmed_incl_phi35_are_suspects"] for k in range(3, 16)},
        "count_all_5_rebuilt_suspects": {k: [by_k[k]["count_all_5_rebuilt_suspects"], by_k[k]["n_subsets"]] for k in range(3, 16)},
        "k_with_all_5_rebuilt_kept_in_100pct_of_subsets": full5,
        "min_k_all_5_rebuilt_kept_in_every_subset_from_then_on": thr["min_k_all5_retained_eq_1.00"],
        "phi35_q2K_dropout_by_k": {r["k"]: r["suspect_dropout_rate"][A1.PHI] for r in per_k if r["suspect_dropout_rate"][A1.PHI] > 0},
        "phi35_q2K_dropout_count_by_k": {r["k"]: r["suspect_dropout_count"][A1.PHI] for r in per_k if r["suspect_dropout_count"][A1.PHI] > 0},
        "llama_q3_K_S_dropout_by_k": llama_q3,
        "llama_q3_K_S_dropout_range_k3_14": rng_of(LLAMA[1], range(3, 15)),
        "llama_q3_K_S_dropout_min_at_k": [k for k in range(3, 15) if llama_q3[k] == min(llama_q3[j] for j in range(3, 15))],
        "llama_q3_K_S_dropout_max_at_k": [k for k in range(3, 15) if llama_q3[k] == max(llama_q3[j] for j in range(3, 15))],
        "llama_q3_K_S_dropout_nonzero_k": nz(LLAMA[1]),
        "llama_q2_K_dropout_by_k": llama_q2,
        "llama_q2_K_dropout_max": max(llama_q2.values()),
        "llama_q2_K_dropout_max_at_k": [k for k, v in llama_q2.items() if v == max(llama_q2.values())],
        "llama_q2_K_dropout_nonzero_k": nz(LLAMA[0]),
        "mean_jaccard_flags_k5": by_k[5]["jaccard_flags_vs_full"]["mean"],
        "mean_jaccard_flags_k10": by_k[10]["jaccard_flags_vs_full"]["mean"],
        "calibration_94pct": calib["frac_suites_flagging_ge1_healthy"],
    }
    ph = pod_a1["headline"]
    vs_pod = {
        "source": "../a1_rescored.json (pod rescore, enumerate if C(15,k) <= 3003 else 2000 draws)",
        "mean_jaccard_flags_k5": [ph["mean_jaccard_flags"]["5"], headline["mean_jaccard_flags_k5"]],
        "mean_jaccard_flags_k10": [ph["mean_jaccard_flags"]["10"], headline["mean_jaccard_flags_k10"]],
        "min_k_all_5_rebuilt_kept": [ph["min_k_all_5_rebuilt_kept_in_every_subset_from_then_on"],
                                     headline["min_k_all_5_rebuilt_kept_in_every_subset_from_then_on"]],
        "llama_q3_K_S_dropout_range_k3_14": [ph["llama_q3_K_S_dropout_range_k3_14"], headline["llama_q3_K_S_dropout_range_k3_14"]],
        "llama_q2_K_dropout_max": [ph["llama_q2_K_dropout_max"], headline["llama_q2_K_dropout_max"]],
        "llama_q2_K_dropout_nonzero_k": [ph["llama_q2_K_dropout_nonzero_k"], headline["llama_q2_K_dropout_nonzero_k"]],
        "phi35_q2K_dropout_by_k": [ph["phi35_q2K_dropout_by_k"], headline["phi35_q2K_dropout_by_k"]],
    }

    # ---- REGROUP: compare with the serial A1 under the released size_key grouping (same scores and settings)
    ser_a1 = json.load(open(A1_SERIAL))
    diffs = []
    for mine, theirs in zip(jnorm(per_k), ser_a1["per_k"]):
        assert mine["k"] == theirs["k"]
        for key_, v in theirs.items():
            if mine.get(key_) != v:
                diffs.append({"k": theirs["k"], "metric": key_, "size_key": v, "checkpoint": mine.get(key_)})
    hl_s, hl_m = ser_a1["headline"], jnorm(headline)
    vs_size_key = {
        "source": relpath_out(A1_SERIAL) + " (serial scores, every subset enumerated, analyze.py size_key grouping)",
        "per_k_metrics_compared": sum(len(r) for r in ser_a1["per_k"]),
        "per_k_differences": diffs,
        "metrics_that_differ": sorted({d["metric"] for d in diffs}),
        "headline_differences": {k: [hl_s.get(k), hl_m.get(k)] for k in sorted(set(hl_s) | set(hl_m)) if hl_s.get(k) != hl_m.get(k)},
        "k14_leave_one_out_identical": jnorm(k14) == ser_a1["k14_leave_one_out"],
        "stability_thresholds_identical": jnorm(thr) == ser_a1["stability_thresholds"],
        "full_suite_reference_identical": {k: v == ser_a1["full_suite_reference"].get(k) for k, v in
                                           jnorm({"flags": sorted(tags[i] for i in flag15),
                                                  "suspects": sorted(tags[i] for i in susp15),
                                                  "stage_two_classes_of_flagged": dict(Counter(cls15.values()))}).items()},
        "llama_dropout_reasons_identical": jnorm(llama_reasons) == ser_a1["llama_dropout_reasons"],
        "phi35_dropouts_identical": jnorm(phi_drops) == ser_a1["phi35_q2K_dropouts"]["subsets"],
        "class_distribution_all_305": [ser_a1["verification_k15_serial"]["class_distribution_all_305"], dict(all_cls)],
    }

    out = {
        "analysis": "A1 part 1 (census suite-size curve) on serial census scores (census_smoke_serial.jsonl), "
                    "all subsets enumerated, checkpoint-identity baseline groups (regroup)",
        "meta": {
            "seed": SEED, "enum_max": ENUM_MAX, "n_draws": N_DRAWS,
            "sampling": "for each k = 3..15 all C(15,k) subsets are enumerated (enum_max = 6435 = C(15,7) = C(15,8)); "
                        "no random draws, every per-k value is exact",
            "rules": "a1_analysis.stage_one_flag / stage_two (scaled: flag s < 0.6k; suspect 15s <= 2k and 15b >= 8k; "
                     "healthy s/b >= 0.6), analyze.py HIGH baseline siblings, grouped by checkpoint identity "
                     "(full tag minus quantization suffix)",
            "grouping": "checkpoint identity (35 groups); validation against the released file uses size_key",
            "per_task_source": "census_smoke_serial.jsonl per_task for the 15 suite tasks, 305 ollama-official tags; "
                               "all other row fields from results/audit_scored.jsonl",
            "reference": "full 15-task suite on serial scores: 39 flags, 7 suspects",
            "rebuilt_5": REBUILT_5, "llama_suspects": LLAMA,
            "reused_from": relpath_out(A1_PY),
            "python": platform.python_version(),
            "inputs_sha256": {relpath_out(p): input_sha256(p) for p in (A1_PY, A1.CENSUS, RESCORE, TUNING_HE, TUNING_MBPP,
                                                             A1.SUITE_FILE, A1.ANALYZE_PY, NUMBERS, A1_SERIAL)},
        },
        "validation_reproduces_released_a1": validation,
        "verification_k15_serial": verification,
        "full_suite_reference": {"flags": sorted(tags[i] for i in flag15),
                                 "suspects": sorted(tags[i] for i in susp15),
                                 "stage_two_classes_of_flagged": dict(Counter(cls15.values()))},
        "headline": headline,
        "vs_pod_rescore_a1": vs_pod,
        "vs_serial_a1_size_key_grouping": vs_size_key,
        "per_k": per_k,
        "k14_leave_one_out": k14,
        "phi35_q2K_dropouts": {"subsets": phi_drops, "high_precision_siblings_failed_tasks": hp_phi,
                               "note": "phi3.5 q2_K scores 0; it leaves the suspect class only when the median of its "
                                       "q6_K/q8_0/fp16 siblings on the subset falls below 8k/15"},
        "llama_dropout_reasons": llama_reasons,
        "stability_thresholds": thr,
        "cross_check_serial_with_released_settings_1000": legacy_serial,
        "calibration_94pct_check": calib,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1)

    # ---- compact summary
    print(f"validation: released A1 reproduced exactly from original scores: {validation['reproduces_released_a1_exactly']}"
          f" ({validation['per_k_metrics_compared']} per-k values, k14 LOO, thresholds)")
    print(f"serial k=15: flags {len(flag15)} (original 50, pod 43; left vs pod: {verification['flags_pod_rescore_not_serial']}), "
          f"suspects {len(susp15)}, classes {dict(all_cls)}, dead tasks {verification['tasks_passed_by_no_artifact']}")
    print(f"settings: every subset enumerated (cap {ENUM_MAX})")
    print("k  subsets   J_flags  J_susp  all5            llama_q2_K  llama_q3_K_S  phi35_q2_K")
    for r in per_k:
        d = r["suspect_dropout_rate"]
        print(f"{r['k']:<2} {r['n_subsets']:>5}{'*' if r['enumerated'] else ' '}   {r['jaccard_flags_vs_full']['mean']:.3f}    "
              f"{r['jaccard_suspects_vs_full']['mean']:.3f}   {r['frac_all_5_confirmed_incl_phi35_are_suspects']:.4f} "
              f"({r['count_all_5_rebuilt_suspects']:>4}) {d[LLAMA[0]]:.4f}      {d[LLAMA[1]]:.4f}        {d[A1.PHI]:.4f}")
    print("headline:", json.dumps({k: v for k, v in headline.items()
                                   if k not in ("mean_jaccard_flags", "mean_jaccard_suspects", "frac_all_5_rebuilt_suspects",
                                                "count_all_5_rebuilt_suspects", "llama_q3_K_S_dropout_by_k", "llama_q2_K_dropout_by_k")}))
    print("vs pod A1:", json.dumps(vs_pod))
    print("llama drop-out reasons:", json.dumps({t: (v["total"], v["share_score_above_cap"]) for t, v in llama_reasons.items()}))
    print("cross-check (released 1000-draw settings, serial scores): J_flags k5 %.3f k10 %.3f"
          % (legacy_serial[2]["mean_jaccard_flags"], legacy_serial[7]["mean_jaccard_flags"]))
    print(f"calibration 94% figure: {calib['frac_suites_flagging_ge1_healthy']} {calib['wilson95']}, "
          f"part2 identical to released: {calib['part2_identical_to_released']}, HE per-task diffs: "
          f"{calib['humaneval_per_task_differences_serial_vs_pool']}, P1 hashes unchanged: {calib['p1_eval_files_sha256_unchanged']}")
    print(f"MBPP healthy range serial {calib['mbpp_healthy_rate_range_pct_serial']} released "
          f"{calib['mbpp_healthy_rate_range_pct_released']}, defective {calib['mbpp_defective_serial']}, "
          f"part3 identical: {calib['part3_mbpp_identical_to_released']}")
    print("census-vs-calibration overlap (serial):", json.dumps(calib["census_vs_calibration_overlap_summary_serial"]))
    print("vs serial A1 (size_key grouping):", json.dumps({k: v for k, v in vs_size_key.items() if k != "per_k_differences"}))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
