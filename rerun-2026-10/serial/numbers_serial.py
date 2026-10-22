#!/usr/bin/env python3
"""Every number the revised paper (v3: TrustAI-BD submission and arXiv v2) cites, from SERIAL scores.

Copy of ../numbers_v3.py whose EvalPlus scores come from the serial re-scoring (serial_rescore.py, one
evaluation at a time, default EvalPlus time limits) instead of the pool-scored files:

  census 15-task scores   census_smoke_serial.jsonl     (was pod-results/census_rescore.jsonl)
  census full 164 tasks   census_full164_serial.jsonl   (was results/fullrun_scores.jsonl)
  rerun results-*         rerun_<set>_serial.jsonl      (was pod-results/results-*/scored.jsonl)
  paper-1 tuning set      tuning_p1_*_serial.jsonl      (was paper-1 *_eval_results.json)

Every rule is unchanged: classification reuses analysis/analyze.py (size_key, HIGH, norm_*, wilson) and
the classify() function below is the one in numbers_v3.py. Non-EvalPlus inputs (output statistics,
generation times, perplexity, tensor comparisons) are read from the same raw files as numbers_v3.py.
The keys of numbers_v3.json are kept (the "_rescored" keys now hold the serial values); the keys added
for the serial pass are listed in ADDED_KEYS at the end. numbers_v3.json is read only for comparison.

Writes numbers_serial.json next to this file and prints a summary.
"""
import importlib.util, json, os, re, statistics
from collections import Counter, defaultdict
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))                 # paper-v3/analysis/serial
P2 = os.environ.get("QUANTCHECK_ROOT", os.path.abspath(os.path.join(HERE, "..", "..")))  # repository root
V3 = os.environ.get("QUANTCHECK_ANALYSIS_DIR", os.path.abspath(os.path.join(HERE, "..", "analysis")))  # numbers_v3.json
RERUN = os.environ.get("QUANTCHECK_RERUN_DIR", os.path.abspath(os.path.join(HERE, "..")))   # rerun-2026-10/: ppl, tensors
SUITE = json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"]
HELDOUT = json.load(open(os.path.join(P2, "heldout_49.json")))

spec = importlib.util.spec_from_file_location("analyze", os.path.join(P2, "analysis", "analyze.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def serial(name):
    """One serially scored set; one record per (id, setting)."""
    rows = jl(os.path.join(HERE, f"{name}_serial.jsonl"))
    keys = [(r["id"], r.get("setting")) for r in rows]
    assert len(keys) == len(set(keys)), name
    for r in rows:
        assert r["n_pass"] == sum(1 for v in r["per_task"].values() if v), (name, r["id"])
    return rows


def wilson(k, n):
    p, lo, hi = A.wilson(k, n)
    return {"k": k, "n": n, "rate": round(p, 4), "lo": round(lo, 4), "hi": round(hi, 4)}


V3N = json.load(open(os.path.join(V3, "numbers_v3.json")))      # comparison only

N = {}
scored = jl(os.path.join(P2, "results", "audit_scored.jsonl"))    # census rows: tags, channel, output stats
official = [r for r in scored if r.get("channel") == "ollama-official"]
community = [r for r in scored if r.get("channel") == "hf-community"]
census_serial = serial("census_smoke")
rescore = {r["tag"]: r for r in census_serial}                     # serial 15-task scores (all 334 rows)
assert len(rescore) == 334 and all(r["tag"] in rescore for r in scored)
for r in census_serial:
    assert set(r["per_task"]) == set(SUITE), r["tag"]
fullruns = {r["tag"]: {"full_pass": r["n_pass"], "full_pass_old": r["old_n_pass"]} for r in serial("census_full164")}

N["census"] = {
    "official": len(official), "community": len(community),
    "official_fp16": sum(1 for r in official if "fp16" in r["tag"]),
    "lines": len({A.norm_model(r["tag"]) for r in official}),
    "family_groups": None,
}
N["census"]["official_quantized"] = N["census"]["official"] - N["census"]["official_fp16"]


def reg_group(tag):
    """(registry model line, size) from the tag itself; analyze.size_key merges gemma3's 270m size."""
    name, rest = tag.split(":", 1)
    m = re.match(r"(\d+(?:\.\d+)?[bm])", rest.lower())
    return (name, m.group(1) if m else "?")


N["census"]["lines"] = len({t["tag"].split(":")[0] for t in official})
N["census"]["model_size_groups"] = len({reg_group(r["tag"]) for r in official})


def classify(rows, score):
    fam = defaultdict(list)
    for r in rows:
        fam[A.size_key(r["tag"])].append(r)
    base = {}
    for k, g in fam.items():
        hi = [score(x) for x in g if any(h in x["tag"] for h in A.HIGH)]
        base[k] = statistics.median(hi) if hi else None
    cls = {}
    for r in rows:
        k = A.size_key(r["tag"]); b = base[k]; s = score(r)
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
    return cls, base


def orig(r):
    return r["smoke_pass"]


def fixed(r):
    """Serial 15-task score (the name is kept from numbers_v3.py)."""
    pt = rescore[r["tag"]]["per_task"]
    return sum(1 for t in SUITE if pt.get(t))


def pod(r):
    """The pod rescore (census_rescore.jsonl) as stored in the serial file's old_n_pass; comparison only."""
    return rescore[r["tag"]]["old_n_pass"]


assert all(rescore[r["tag"]]["old_n_pass_census_original"] == r["smoke_pass"] for r in scored)

CLS = {}
for name, fn in (("original", orig), ("rescored", fixed), ("pod_rescore_v3", pod)):
    cls, base = classify(official, fn)
    CLS[name] = (cls, base)
    N[f"classes_{name}"] = dict(Counter(cls.values()))
    N[f"stage1_flags_{name}"] = sum(1 for r in official if fn(r) < 9)
    N[f"suspects_{name}"] = sorted(t for t, c in cls.items() if c == "SUSPECT")
# the pod-rescore classification must reproduce numbers_v3.json exactly
assert N["classes_pod_rescore_v3"] == V3N["classes_rescored"]
assert N["stage1_flags_pod_rescore_v3"] == V3N["stage1_flags_rescored"] == 43
assert N["suspects_pod_rescore_v3"] == V3N["suspects_rescored"]
assert N["classes_original"] == V3N["classes_original"] and N["stage1_flags_original"] == V3N["stage1_flags_original"]

N["he15_pass_rescored"] = sum(1 for r in official if rescore[r["tag"]]["per_task"].get("HumanEval/15"))
N["artifacts_changed_by_rescore"] = sum(1 for r in official if fixed(r) != orig(r))

sus = N["suspects_rescored"]
N["suspects"] = [{"tag": t, "smoke_rescored": fixed(next(r for r in official if r["tag"] == t)),
                  "full164": fullruns.get(t, {}).get("full_pass")} for t in sus]
N["nonfunctional"] = wilson(len(sus), len(official))
groups = {reg_group(t) for t in sus}
N["nonfunctional_groups"] = wilson(len(groups), N["census"]["model_size_groups"])
N["nonfunctional_incidents"] = sorted("/".join(g) for g in groups)
lowbit_small = [r for r in official if A.tag_quant(r["tag"]) in ("q2_k", "q3_k_s", "q3_k_m", "q3_k_l")
                and float(A.norm_size(r["tag"]) if A.norm_size(r["tag"]) != "?" else 99) <= 4]
N["lowbit_le4b"] = {"artifacts": len(lowbit_small), "nonfunctional": sum(1 for r in lowbit_small if r["tag"] in sus)}

# Screening cost: summed per-task generation time per official artifact (census, CUDA)
res = {r["tag"]: r for r in jl(os.path.join(P2, "results", "audit_results.jsonl"))}
gen = [sum(m["wall_s"] for m in res[r["tag"]]["metrics"]) for r in official if res.get(r["tag"], {}).get("metrics")]
N["screen_seconds"] = {"median": round(statistics.median(gen), 1), "min": round(min(gen), 1), "max": round(max(gen), 1),
                       "n": len(gen)}

# Community channel (same rule as numbers_v3: >= 9 of 15, now on the serial score)
N["community_healthy_cuda"] = sum(1 for r in community if fixed(r) >= 9)

# Rerun results: serial file per pod results folder
SET_OF = {"results": "rerun_results", "results-r2": "rerun_r2", "results-r3": "rerun_r3", "results-r3b": "rerun_r3b",
          "results-r5": "rerun_r5", "results-r6": "rerun_r6", "results-p0": "rerun_p0", "results-p0c": "rerun_p0c",
          "results-g1": "rerun_g1"}
_SER = {d: serial(s) for d, s in SET_OF.items()}


def tab(dirname, setting=None, field="n_pass"):
    out = {}
    for r in _SER[dirname]:
        i, s = r["id"], r["setting"]
        if setting is None or s == setting:
            out[i if setting else (i, s)] = r[field]
    return out


def per_task(dirname, rid, setting):
    return next(r for r in _SER[dirname] if r["id"] == rid and r["setting"] == setting)["per_task"]


N["R1"] = tab("results", "base")
N["R2"] = {f"{i}|{s}": v for (i, s), v in tab("results-r2").items()}
N["R5"] = tab("results-r5", "base")
N["R6"] = tab("results-r6", "full164")
N["P0_smoke"] = tab("results-p0", "base")
N["P0c"] = tab("results-p0c", "full164")
N["G1"] = tab("results-g1", "base")
# same runs as numbers_v3 (the serial files' old_n_pass is the pool score numbers_v3 read)
for key, d, s in (("R1", "results", "base"), ("R5", "results-r5", "base"), ("R6", "results-r6", "full164"),
                  ("P0_smoke", "results-p0", "base"), ("P0c", "results-p0c", "full164"), ("G1", "results-g1", "base")):
    assert tab(d, s, "old_n_pass") == V3N[key], key
assert {f"{i}|{s}": v for (i, s), v in tab("results-r2", None, "old_n_pass").items()} == V3N["R2"]

fn_scores = []
for d in ("results-r3", "results-r3b"):
    fn_scores += list(tab(d, "heldout49").values())
N["fn_audit"] = {"new": len(fn_scores), "v1": 10, "total": len(fn_scores) + 10,
                 "min": min(fn_scores), "max": max(fn_scores), "median": statistics.median(fn_scores),
                 "misses": sum(1 for s in fn_scores if s <= 2)}
N["fn_audit"]["wilson"] = wilson(0, N["fn_audit"]["total"])
N["fn_audit_v1_wilson"] = wilson(0, 10)

# Perplexity
ppl = {}
for f in sorted(os.listdir(os.path.join(RERUN, "ppl"))):
    t = open(os.path.join(RERUN, "ppl", f)).read()
    m = re.findall(r"Final estimate: PPL = ([0-9.]+)", t)
    if m:
        ppl[f[:-4]] = float(m[-1])
N["ppl"] = ppl

# Tensor identity
N["tensor_identity"] = [ {k: r[k] for k in ("a", "b", "n_tensors", "identical_tensors", "type_differs", "same_type_bytes_differ")}
                         for f in ("p0b_tensor_compare.jsonl", "p0f_compare.jsonl", "g1_tensor_compare.jsonl")
                         for r in jl(os.path.join(RERUN, f))]

# Suite robustness (A1): keys of the released file, as in numbers_v3 (the serial A1 is a1_serial.json)
a1 = json.load(open(os.path.expanduser("~/Documents/paper/p2-v2-work/rerun-2026-10/a1/a1_results.json")))
N["A1_keys"] = sorted(a1.keys())[:30]

# =====================================================================================================
# Added for the serial pass
# =====================================================================================================
cls_s, base_s = CLS["rescored"]
cls_p, base_p = CLS["pod_rescore_v3"]
cls_o, base_o = CLS["original"]
by_tag = {r["tag"]: r for r in official}

N["stage1_flags_serial"] = {
    "n": N["stage1_flags_rescored"], "numbers_v3": V3N["stage1_flags_rescored"], "original": N["stage1_flags_original"],
    "flags": sorted(r["tag"] for r in official if fixed(r) < 9),
    "left_vs_numbers_v3": sorted(r["tag"] for r in official if pod(r) < 9 <= fixed(r)),
    "new_vs_numbers_v3": sorted(r["tag"] for r in official if fixed(r) < 9 <= pod(r)),
    "left_vs_original": sorted(r["tag"] for r in official if orig(r) < 9 <= fixed(r)),
    "unflagged": sum(1 for r in official if fixed(r) >= 9),
}
N["classes_serial"] = {
    "counts": N["classes_rescored"], "counts_numbers_v3": V3N["classes_rescored"],
    "counts_unchanged": N["classes_rescored"] == V3N["classes_rescored"],
    "suspects": sus, "suspects_unchanged": sus == V3N["suspects_rescored"],
    "per_class": {c: sorted(t for t, x in cls_s.items() if x == c) for c in sorted(set(cls_s.values())) if c != "HEALTHY"},
}


def _chg(ref_cls, ref_base, ref_score):
    out = []
    for r in official:
        t = r["tag"]
        if cls_s[t] != ref_cls[t]:
            k = A.size_key(t)
            out.append({"tag": t, "class_before": ref_cls[t], "class_serial": cls_s[t],
                        "score_before": ref_score(r), "score_serial": fixed(r),
                        "baseline_before": ref_base[k], "baseline_serial": base_s[k],
                        "ratio_serial": round(fixed(r) / base_s[k], 4) if base_s[k] else None})
    return out


N["class_changes_vs_numbers_v3"] = _chg(cls_p, base_p, pod)
N["class_changes_vs_original_census"] = _chg(cls_o, base_o, orig)
N["baselines_changed_vs_numbers_v3"] = {"/".join(k): [base_p[k], base_s[k]] for k in base_s if base_p[k] != base_s[k]}

N["he15_pass_official"] = {"serial": N["he15_pass_rescored"], "numbers_v3": V3N["he15_pass_rescored"], "original": 0,
                           "of": len(official)}
assert not any(r["per_task"].get("HumanEval/15") for r in official)       # original census: 0


def _gains(ref_pt):
    """per-artifact task changes, serial vs a reference per-task dict."""
    gained, lost = Counter(), Counter()
    n_gain = Counter()
    for r in official:
        sp = rescore[r["tag"]]["per_task"]
        g = [t for t in SUITE if sp[t] and not ref_pt(r)[t]]
        l = [t for t in SUITE if ref_pt(r)[t] and not sp[t]]
        gained.update(g); lost.update(l)
        if g or l:
            n_gain[len(g) - len(l)] += 1
    return gained, lost, n_gain


def _pod_pt(r):
    x = rescore[r["tag"]]
    pt = dict(x["per_task"])
    for f in x["flips"]:
        pt[f["task_id"]] = f["old"] == "pass"
    return pt


g_o, l_o, n_o = _gains(lambda r: {t: bool(r["per_task"][t]) for t in SUITE})
g_p, l_p, n_p = _gains(_pod_pt)
assert all(sum(1 for t in SUITE if _pod_pt(r)[t]) == pod(r) for r in official)
N["artifacts_changed_vs_original_census"] = {
    "n": N["artifacts_changed_by_rescore"], "numbers_v3": V3N["artifacts_changed_by_rescore"],
    "by_net_tasks_gained": {str(k): v for k, v in sorted(n_o.items())},
    "tasks_gained": dict(g_o), "tasks_lost": dict(l_o), "any_loss": bool(l_o),
    "gaining_more_than_one": sorted(r["tag"] for r in official if fixed(r) - orig(r) > 1),
    "gaining_without_he15": sorted(r["tag"] for r in official if fixed(r) != orig(r)
                                   and not rescore[r["tag"]]["per_task"]["HumanEval/15"]),
}
N["artifacts_changed_vs_numbers_v3"] = {"n": sum(1 for r in official if fixed(r) != pod(r)),
                                        "tasks_gained": dict(g_p), "tasks_lost": dict(l_p)}

# ---- RQ3 output-statistic rules (statistics from audit_scored.jsonl, classes from the serial scores)
SUS7 = set(sus)
others = [r for r in official if r["tag"] not in SUS7]
assert len(others) == 298


def rule(f):
    tp = sorted(r["tag"] for r in official if r["tag"] in SUS7 and f(r))
    fp = sorted(r["tag"] for r in others if f(r))
    return {"hits": len(tp), "of": len(SUS7), "hit_tags": tp, "false_positives": len(fp), "fp_of": len(others),
            "fp_share": round(len(fp) / len(others), 4), "fp_classes": dict(Counter(cls_s[t] for t in fp)),
            "fp_classes_numbers_v3": dict(Counter(cls_p[t] for t in fp)),
            "fp_tags": [[t, cls_s[t]] for t in fp]}


rq3 = {
    "trunc_ge_0.2": rule(lambda r: r["trunc_frac"] >= 0.2),
    "rep6_ge_0.2": rule(lambda r: r["rep6_share_mean"] >= 0.2),
    "either_ge_0.3": rule(lambda r: r["trunc_frac"] >= 0.3 or r["rep6_share_mean"] >= 0.3),
}
missed = sorted(SUS7 - set(rq3["either_ge_0.3"]["hit_tags"]))
healthy_s = [r for r in official if cls_s[r["tag"]] == "HEALTHY"]
healthy_p = [r for r in official if cls_p[r["tag"]] == "HEALTHY"]


def share(rows, thr):
    n = sum(1 for r in rows if r["rep6_share_mean"] >= thr)
    return {"n": n, "of": len(rows), "share": round(n / len(rows), 4)}


lo_thr = min(by_tag[t]["rep6_share_mean"] for t in missed)    # catches all three
hi_thr = max(by_tag[t]["rep6_share_mean"] for t in missed)    # lowest bar that catches at least one
rq3["missed_by_either_ge_0.3"] = {
    "tags": missed, "trunc_frac": {t: by_tag[t]["trunc_frac"] for t in missed},
    "rep6_share_mean": {t: by_tag[t]["rep6_share_mean"] for t in missed},
    "never_hit_token_cap": all(by_tag[t]["trunc_frac"] == 0 for t in missed),
    "healthy_firing_at_threshold_catching_at_least_one": {"threshold": hi_thr, **share(healthy_s, hi_thr),
                                                          "numbers_v3_classes": share(healthy_p, hi_thr)},
    "healthy_firing_at_threshold_catching_all_three": {"threshold": lo_thr, **share(healthy_s, lo_thr),
                                                       "numbers_v3_classes": share(healthy_p, lo_thr)},
    "per_missed_tag": {t: {"threshold": by_tag[t]["rep6_share_mean"], **share(healthy_s, by_tag[t]["rep6_share_mean"])}
                       for t in missed},
    "note": "the paper's 'at least 4.4% of healthy artifacts' is the lowest repetition bar that catches any of the "
            "three (their largest rep6 share)",
}
N["rq3_output_rules"] = rq3

# ---- miss audit and the 1.5B held-out numbers
heldout_all = {**tab("results-r3", "heldout49"), **tab("results-r3b", "heldout49")}
N["fn_audit_serial"] = {**N["fn_audit"], "numbers_v3": V3N["fn_audit"],
                        "changed_runs": {k: [o, heldout_all[k]] for k, o in
                                         {**tab("results-r3", "heldout49", "old_n_pass"),
                                          **tab("results-r3b", "heldout49", "old_n_pass")}.items() if o != heldout_all[k]}}
sens = serial("sensitivity")
assert all(set(r["per_task"]) == set(HELDOUT) for r in sens)
N["fn_audit_v1_sample_serial"] = {"n": len(sens), "min": min(r["n_pass"] for r in sens), "max": max(r["n_pass"] for r in sens),
                                  "scores": {r["id"]: r["n_pass"] for r in sens},
                                  "changed": [r["id"] for r in sens if r["n_pass"] != r["old_n_pass"]]}
N["heldout_1p5b"] = {
    "qwen2.5-coder:1.5b q2_K": heldout_all["fn-qwen2.5-coder_1.5b-instruct-q2_K"],
    "qwen2.5-coder:1.5b q3_K_S": heldout_all["fn-qwen2.5-coder_1.5b-instruct-q3_K_S"],
    "qwen2.5-coder:1.5b q4_0": heldout_all["fn-qwen2.5-coder_1.5b-instruct-q4_0"],
    "of": len(HELDOUT),
}
# sampling frame of the miss audit: set on the ORIGINAL census flags (255 unflagged) minus the 22 tuning configs
TUNING_AVAILABLE = os.path.exists(os.path.join(HERE, "tuning_p1_humaneval_serial.jsonl"))
if TUNING_AVAILABLE:
    tuning_tags = {r["id"].replace("_", ":", 1) for r in serial("tuning_p1_humaneval")}
else:  # release layout: names only (tuning_configs.json)
    tuning_tags = {i.replace("_", ":", 1) for i in json.load(open(os.path.join(HERE, "tuning_configs.json")))["ids"]}
tun_in = [r for r in official if r["tag"] in tuning_tags]
N["miss_audit_frame"] = {
    "tuning_configs_in_census": len(tun_in),
    "frame_original_unflagged_minus_tuning": sum(1 for r in official if orig(r) >= 9 and r["tag"] not in tuning_tags),
    "serial_unflagged_minus_tuning": sum(1 for r in official if fixed(r) >= 9 and r["tag"] not in tuning_tags),
    "numbers_v3_unflagged_minus_tuning": sum(1 for r in official if pod(r) >= 9 and r["tag"] not in tuning_tags),
    "bound_5.5pct_times_frame": round(0.055 * sum(1 for r in official if orig(r) >= 9 and r["tag"] not in tuning_tags), 1),
    "bound_5.5pct_times_serial_unflagged": round(0.055 * sum(1 for r in official if fixed(r) >= 9 and r["tag"] not in tuning_tags), 1),
}

# ---- every /164 number the paper uses
R6, P0c = N["R6"], N["P0c"]
full = {
    "suspects": {t: fullruns[t]["full_pass"] for t in sus},
    "own_imatrix_wikitext": {"Q2_K": R6["cal-qwen3b-Q2_K"], "Q3_K_S": R6["cal-qwen3b-Q3_K_S"],
                             "Q3_K_M": R6["cal-qwen3b-Q3_K_M"], "Q3_K_L": R6["cal-qwen3b-Q3_K_L"]},
    "own_imatrix_code": {"Q2_K": P0c["codeimat-qwen3b-Q2_K"], "Q3_K_S": P0c["codeimat-qwen3b-Q3_K_S"],
                         "Q3_K_M": P0c["codeimat-qwen3b-Q3_K_M"], "Q3_K_L": P0c["codeimat-qwen3b-Q3_K_L"]},
    "bartowski_qwen": {"Q2_K": R6["imat-qwen3b-Q2_K"], "Q3_K_S": P0c["imat-qwen3b-Q3_K_S"],
                       "Q3_K_M": P0c["imat-qwen3b-Q3_K_M"], "Q3_K_L": P0c["imat-qwen3b-Q3_K_L"]},
    "awq_qwen": {"q2_K": R6["awq-qwen3b-q2_k"], "q3_K_M": R6["awq-qwen3b-q3_k_m"]},
    "phi35": {"library_mix_rebuild_libmix": P0c["libmix-phi35-Q2_K"], "plain_current_mix": P0c["plain-phi35-Q2_K"],
              "wikitext_imatrix_cal": P0c["cal-phi35-Q2_K"], "bartowski": P0c["imat-phi35-Q2_K"],
              "registry_q4_K_M": P0c["lib-phi35-q4_K_M"],
              "plain_Q3_K_S": P0c["plain-phi35-Q3_K_S"], "plain_Q3_K_M": P0c["plain-phi35-Q3_K_M"],
              "cal_Q3_K_S": P0c["cal-phi35-Q3_K_S"], "cal_Q3_K_M": P0c["cal-phi35-Q3_K_M"]},
    "plain_qwen_Q4_K_M_control": R6["plain-qwen3b-Q4_K_M"],
    "registry_4bit": {"qwen2.5-coder:3b q4_K_M": R6["lib-qwen3b-q4_K_M"], "phi3.5 q4_K_M": P0c["lib-phi35-q4_K_M"]},
    "deepseek_coder_1.3b_tags": {t: v["full_pass"] for t, v in fullruns.items() if t.startswith("deepseek-coder:1.3b")},
    "llama3.2_1b_q3_K_S": fullruns["llama3.2:1b-instruct-q3_K_S"]["full_pass"],
    "census_full164_all": {t: v["full_pass"] for t, v in fullruns.items()},
    "census_full164_changed": {t: [v["full_pass_old"], v["full_pass"]] for t, v in fullruns.items()
                               if v["full_pass"] != v["full_pass_old"]},
    "native_deepseek_6.7b": {r["id"]: {"full164": r["n_pass"], "smoke15_subset": r.get("n_pass_smoke15")}
                             for r in serial("native")},
}
own3 = [full["own_imatrix_wikitext"][l] for l in ("Q2_K", "Q3_K_M", "Q3_K_L")] + \
       [full["own_imatrix_code"][l] for l in ("Q2_K", "Q3_K_M", "Q3_K_L")]
full["derived"] = {
    "own_imatrix_three_rescued_range": [min(own3), max(own3)],
    "own_imatrix_three_rescued_pct": [round(100 * min(own3) / 164, 1), round(100 * max(own3) / 164, 1)],
    "Q2_K_own_range": sorted([full["own_imatrix_wikitext"]["Q2_K"], full["own_imatrix_code"]["Q2_K"]]),
    "Q3_K_M_own_range": sorted([full["own_imatrix_wikitext"]["Q3_K_M"], full["own_imatrix_code"]["Q3_K_M"]]),
    "Q3_K_L_own_range": sorted([full["own_imatrix_wikitext"]["Q3_K_L"], full["own_imatrix_code"]["Q3_K_L"]]),
    "Q3_K_S_all_calibrations_range": [min(full["own_imatrix_wikitext"]["Q3_K_S"], full["own_imatrix_code"]["Q3_K_S"],
                                          full["bartowski_qwen"]["Q3_K_S"]),
                                      max(full["own_imatrix_wikitext"]["Q3_K_S"], full["own_imatrix_code"]["Q3_K_S"],
                                          full["bartowski_qwen"]["Q3_K_S"])],
    "registry_qwen_4bit_pct": round(100 * full["registry_4bit"]["qwen2.5-coder:3b q4_K_M"] / 164, 1),
    "best_q2_K_pct": round(100 * max(full["own_imatrix_wikitext"]["Q2_K"], full["own_imatrix_code"]["Q2_K"]) / 164, 1),
    "suspects_max": max(full["suspects"].values()),
    "nonfunctional_under_10pct": all(v < 16.4 for v in full["suspects"].values()),
}
N["full164"] = full

# ---- Table IV (attribution), cells as printed
R1, R5, P0 = N["R1"], N["R5"], N["P0_smoke"]
hf = {r["tag"]: r for r in census_serial if r["channel"] == "hf-adjudication"}
unsloth = {lvl: fixed(hf[f"hf:unsloth/Llama-3.2-1B-Instruct-GGUF/Llama-3.2-1B-Instruct-{lvl}.gguf"]) for lvl in ("Q2_K", "Q3_K_S")}
T4 = {}
for lvl, L in (("q2_K", "Q2_K"), ("q3_K_S", "Q3_K_S"), ("q3_K_M", "Q3_K_M"), ("q3_K_L", "Q3_K_L")):
    tag = f"qwen2.5-coder:3b-instruct-{lvl}"
    best = [full["own_imatrix_wikitext"][L], full["own_imatrix_code"][L], full["bartowski_qwen"][L]]
    if lvl in ("q2_K", "q3_K_M"):
        best.append(full["awq_qwen"][lvl])
    T4[tag] = {"library": fixed(by_tag[tag]), "library_164": fullruns[tag]["full_pass"], "plain": R1[f"plain-qwen3b-{L}"],
               "own_imatrix": f"{R5[f'cal-qwen3b-{L}']}, {P0[f'codeimat-qwen3b-{L}']}",
               "third_party": R1[f"imat-qwen3b-{L}"],
               "qwen_awq": R1.get({"q2_K": "awq-qwen3b-q2_k", "q3_K_M": "awq-qwen3b-q3_k_m"}.get(lvl, ""), "--"),
               "best_cal_164": max(best)}
tag = "phi3.5:3.8b-mini-instruct-q2_K"
T4[tag] = {"library": fixed(by_tag[tag]), "library_164": fullruns[tag]["full_pass"],
           "plain": f"{P0['libmix-phi35-Q2_K']} ({R1['plain-phi35-Q2_K']})",
           "own_imatrix": f"{R5['cal-phi35-Q2_K']}, {P0['codeimat-phi35-Q2_K']}", "third_party": R1["imat-phi35-Q2_K"],
           "qwen_awq": "--", "best_cal_164": max(P0c["cal-phi35-Q2_K"], P0c["imat-phi35-Q2_K"])}
for lvl in ("q2_K", "q3_K_S"):
    tag = f"llama3.2:1b-instruct-{lvl}"
    T4[tag] = {"library": fixed(by_tag[tag]), "library_164": fullruns[tag]["full_pass"], "plain": "--", "own_imatrix": "--",
               "third_party": f"({unsloth[lvl.upper()]})", "qwen_awq": "--", "best_cal_164": "--"}
N["table_IV_attribution"] = T4
N["table_IV_caption"] = {"phi35_plain_current_mix_164": P0c["plain-phi35-Q2_K"],
                         "phi35_own_imatrix_15": [R5["cal-phi35-Q2_K"], P0["codeimat-phi35-Q2_K"]],
                         "phi35_plain_current_mix_15": R1["plain-phi35-Q2_K"],
                         "phi35_bartowski_15": R1["imat-phi35-Q2_K"], "phi35_library_mix_rebuild_15": P0["libmix-phi35-Q2_K"]}

# ---- Table VI (same recipe, two sizes): library / plain / WikiText imatrix
G1 = N["G1"]
T6 = {}
for lvl in ("q2_K", "q3_K_S", "q3_K_M", "q3_K_L"):
    T6[lvl] = {"1.5B": [G1[f"g1lib-qwen1.5b-{lvl}"], G1[f"g1plain-qwen1.5b-{lvl}"], G1[f"g1imat-qwen1.5b-{lvl}"]],
               "3B": [R1[f"lib-qwen3b-{lvl}"], R1[f"plain-qwen3b-{lvl.replace('q', 'Q', 1)}"], R5[f"cal-qwen3b-{lvl.replace('q', 'Q', 1)}"]],
               "1.5B_census_tag": fixed(by_tag[f"qwen2.5-coder:1.5b-instruct-{lvl}"])}
lib_plain_15 = [v for c in T6.values() for v in c["1.5B"][:2]]
N["table_VI_sizes"] = T6
N["table_VI_text"] = {"1.5B_library_and_plain_range": [min(lib_plain_15), max(lib_plain_15)],
                      "1.5B_all_cells_range": [min(v for c in T6.values() for v in c["1.5B"]),
                                               max(v for c in T6.values() for v in c["1.5B"])],
                      "0.5B_G1": {k: v for k, v in G1.items() if "0.5b" in k},
                      "qwen3b_q4_0_tag_15": fixed(by_tag["qwen2.5-coder:3b-instruct-q4_0"])}

# ---- Table VIII (generation settings)
R2 = N["R2"]
SETS = [("base", None), ("ctx4096", "ctx4096"), ("ctx8192", "ctx8192"), ("pred2048", "pred2048"),
        ("t02", ["t02s1", "t02s2", "t02s3"])]


def cell(ids, setting):
    vals = []
    for i in ids:
        vals.append(R1[i] if setting is None else R2[f"{i}|{setting}"])
    return max(vals)


ROWS8 = {"Lib. Qwen-3B q2_K--q3_K_L": ["lib-qwen3b-q2_K", "lib-qwen3b-q3_K_S", "lib-qwen3b-q3_K_M", "lib-qwen3b-q3_K_L"],
         "Lib. phi3.5 q2_K": ["lib-phi35-q2_K"],
         "Plain Qwen-3B Q2_K, Q3_K_M": ["plain-qwen3b-Q2_K", "plain-qwen3b-Q3_K_M"],
         "Plain phi3.5 Q2_K (current mix)": ["plain-phi35-Q2_K"],
         "Lib. Qwen-3B q4_K_M": ["lib-qwen3b-q4_K_M"], "Lib. phi3.5 q4_K_M": ["lib-phi35-q4_K_M"]}
T8 = {}
for row, ids in ROWS8.items():
    T8[row] = {"Base": cell(ids, None), "Ctx 4k": cell(ids, "ctx4096"), "Ctx 8k": cell(ids, "ctx8192"),
               "Cap 2k": cell(ids, "pred2048"), "T0.2": [cell(ids, s) for s in ("t02s1", "t02s2", "t02s3")]}
N["table_VIII_settings"] = T8
N["table_VIII_note"] = "cells hold the maximum over the row's builds (all are 0 for multi-build rows)"

# ---- exact McNemar: phi3.5 plain current mix vs WikiText imatrix, 164 tasks (as gates/r2_verify/mcnemar.py)
def exact(b, c):
    n = b + c; k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def mcnemar(a, b):
    pa, pb = per_task("results-p0c", a, "full164"), per_task("results-p0c", b, "full164")
    assert set(pa) == set(pb) and len(pa) == 164
    x = sum(1 for t in pa if pa[t] and not pb[t]); y = sum(1 for t in pa if pb[t] and not pa[t])
    return {"a": a, "b": b, "a_pass": sum(pa.values()), "b_pass": sum(pb.values()), "a_only": x, "b_only": y,
            "p_exact_two_sided": float(f"{exact(x, y):.4g}")}


N["mcnemar_phi35_plain_vs_wikitext"] = mcnemar("plain-phi35-Q2_K", "cal-phi35-Q2_K")
N["mcnemar_phi35_libmix_vs_bartowski"] = mcnemar("libmix-phi35-Q2_K", "imat-phi35-Q2_K")

# ---- remaining 15-task numbers cited in the text
ds13 = {t: fixed(r) for t, r in by_tag.items() if t.startswith("deepseek-coder:1.3b")}
N["deepseek_coder_1.3b"] = {"smoke_range": [min(ds13.values()), max(ds13.values())], "n_tags": len(ds13),
                            "classes": dict(Counter(cls_s[t] for t in ds13)),
                            "healthy_scores": sorted(ds13[t] for t in ds13 if cls_s[t] == "HEALTHY"),
                            "all_low_baseline_are_ds13": all(t in ds13 for t, c in cls_s.items() if c == "COLLAPSED"),
                            "fp16_full164": fullruns["deepseek-coder:1.3b-instruct-fp16"]["full_pass"]}
comm = {r["tag"]: fixed(r) for r in community}
N["community_serial"] = {"healthy_ge9": sum(v >= 9 for v in comm.values()), "of": len(comm),
                         "failing": {t: v for t, v in comm.items() if v < 9},
                         "ollama_deepseek_6.7b_q3_K_M_q4_K_M": [fixed(by_tag["deepseek-coder:6.7b-instruct-q3_K_M"]),
                                                                fixed(by_tag["deepseek-coder:6.7b-instruct-q4_K_M"])],
                         "hf_adjudication": {t: fixed(r) for t, r in hf.items()}}
metal = {r["id"]: r["n_pass"] for r in serial("metalrep")}
mac = {r["id"]: r["n_pass"] for r in serial("mac")}
N["metal_serial"] = {"metalrep": metal, "mac": mac,
                     "five_rebuilt_suspects_zero_on_metal": all(v == 0 for k, v in {**metal, **mac}.items() if "deepseek" not in k)
                     and len([k for k in {**metal, **mac} if "deepseek" not in k]) == 5}
pretok_other = [t for t in by_tag if t.startswith(("deepseek-coder:6.7b", "starcoder2:15b"))]
N["pretokenizer_other_14"] = {"n": len(pretok_other), "classes": dict(Counter(cls_s[t] for t in pretok_other)),
                              "min_smoke": min(fixed(by_tag[t]) for t in pretok_other)}

if TUNING_AVAILABLE:
    # ---- screen-tuning data (paper-1 configurations, serial)
    he = {r["id"]: r["per_task"] for r in serial("tuning_p1_humaneval")}
    mb = {r["id"]: r["per_task"] for r in serial("tuning_p1_mbpp")}
    DEF = "qwen2.5-coder_3b-instruct-q3_K_M"
    healthy_cfg = [c for c in sorted(he) if c != DEF]
    pool39 = sorted(t for t in sorted(next(iter(he.values()))) if all(he[c][t] for c in healthy_cfg))
    mrate = {c: sum(mb[c].values()) / len(mb[c]) for c in healthy_cfg}
    N["tuning_serial"] = {
        "n_configs": len(he), "n_healthy": len(healthy_cfg),
        "pool_solved_by_all_healthy": len(pool39), "suite_is_first_15_lexicographic": pool39[:15] == SUITE,
        "healthy_suite_all_15": all(sum(he[c][t] for t in SUITE) == 15 for c in healthy_cfg),
        "defective_suite": sum(he[DEF][t] for t in SUITE), "defective_humaneval_plus": sum(he[DEF].values()),
        "mbpp_n": len(mb[DEF]), "mbpp_healthy_rate_min_pct": round(100 * min(mrate.values()), 1),
        "mbpp_healthy_rate_max_pct": round(100 * max(mrate.values()), 1), "mbpp_defective": sum(mb[DEF].values()),
        "humaneval_changed_vs_pool": [r["id"] for r in serial("tuning_p1_humaneval") if r["flips"]],
        "mbpp_changed_vs_pool": {r["id"]: [r["old_n_pass"], r["n_pass"]] for r in serial("tuning_p1_mbpp") if r["n_pass"] != r["old_n_pass"]},
    }
else:  # tuning results not released: keep the committed values, marked as such
    _prev = json.load(open(os.path.join(HERE, "numbers_serial.json")))
    N["tuning_serial"] = dict(_prev.get("tuning_serial", {}), from_committed_file=True)

ADDED_KEYS = ["classes_pod_rescore_v3", "stage1_flags_pod_rescore_v3", "suspects_pod_rescore_v3", "stage1_flags_serial",
              "classes_serial", "class_changes_vs_numbers_v3", "class_changes_vs_original_census", "baselines_changed_vs_numbers_v3",
              "he15_pass_official", "artifacts_changed_vs_original_census", "artifacts_changed_vs_numbers_v3",
              "rq3_output_rules", "fn_audit_serial", "fn_audit_v1_sample_serial", "heldout_1p5b", "miss_audit_frame",
              "full164", "table_IV_attribution", "table_IV_caption", "table_VI_sizes", "table_VI_text", "table_VIII_settings",
              "table_VIII_note", "mcnemar_phi35_plain_vs_wikitext", "mcnemar_phi35_libmix_vs_bartowski", "deepseek_coder_1.3b",
              "community_serial", "metal_serial", "pretokenizer_other_14", "tuning_serial"]
assert set(V3N) <= set(N), sorted(set(V3N) - set(N))
N["_meta"] = {"scores": "serial (serial_rescore.py): one evaluation at a time, default EvalPlus time limits",
              "keys_from_numbers_v3": sorted(V3N), "added_keys": ADDED_KEYS,
              "note": "keys ending in _rescored hold the serial values; *_pod_rescore_v3 reproduce numbers_v3.json"}

out = os.path.join(HERE, "numbers_serial.json")
json.dump(N, open(out, "w"), indent=1, default=str)
for k in ("census", "classes_original", "classes_rescored", "stage1_flags_original", "stage1_flags_rescored",
          "he15_pass_rescored", "artifacts_changed_by_rescore", "suspects", "nonfunctional", "nonfunctional_groups",
          "nonfunctional_incidents", "lowbit_le4b", "screen_seconds", "community_healthy_cuda", "fn_audit"):
    print(k, json.dumps(N[k], default=str))
print("R6", N["R6"]); print("P0c", N["P0c"]); print("G1", N["G1"])
print("class changes vs numbers_v3:", json.dumps(N["class_changes_vs_numbers_v3"]))
print("stage-one flags left vs numbers_v3:", N["stage1_flags_serial"]["left_vs_numbers_v3"])
print("changed vs original:", json.dumps(N["artifacts_changed_vs_original_census"]["by_net_tasks_gained"]),
      N["artifacts_changed_vs_original_census"]["gaining_more_than_one"])
for k in ("trunc_ge_0.2", "rep6_ge_0.2", "either_ge_0.3"):
    x = rq3[k]; print("RQ3", k, x["hits"], x["false_positives"], x["fp_share"], x["fp_classes"])
print("RQ3 missed", json.dumps({k: v for k, v in rq3["missed_by_either_ge_0.3"].items() if k != "note"}))
print("fn_audit_serial", json.dumps(N["fn_audit_serial"]["changed_runs"]), "heldout_1p5b", N["heldout_1p5b"])
print("miss frame", N["miss_audit_frame"])
print("Table VI", json.dumps(T6)); print("Table VIII", json.dumps(T8))
print("McNemar", N["mcnemar_phi35_plain_vs_wikitext"])
print("tuning", json.dumps({k: v for k, v in N["tuning_serial"].items()}))
print("community", json.dumps(N["community_serial"]["failing"]), N["community_serial"]["ollama_deepseek_6.7b_q3_K_M_q4_K_M"])
print("deepseek 1.3b", N["deepseek_coder_1.3b"]); print("pretok other", N["pretokenizer_other_14"])
print("full164 derived", N["full164"]["derived"]); print("full164 changed", N["full164"]["census_full164_changed"])
print(f"wrote {out}")
