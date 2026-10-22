#!/usr/bin/env python3
"""Output-statistic flags, acceptance gate on the census, persistence, repetition score, full-run table.

Independent recomputation from raw records (python3 stdlib only, read-only on all inputs). Paths follow the
repository layout; QUANTCHECK_ROOT, QUANTCHECK_RERUN_DIR, QUANTCHECK_SERIAL_DIR and QUANTCHECK_OUT_DIR override them.
  census rows + output statistics   results/audit_results.jsonl (per-generation metrics) and audit_scored.jsonl
  serial 15-task scores             rerun-2026-10/serial/census_smoke_serial.jsonl
  full 164-task scores              rerun-2026-10/serial/census_full164_serial.jsonl, results/fullrun_scores.jsonl,
                                    rerun-2026-10/results-v1cases/scored_serial.jsonl,
                                    rerun-2026-10/serial/rerun_r6_serial.jsonl, rerun_p0c_serial.jsonl
  classes and RQ3 cross-check       rerun-2026-10/serial/numbers_regroup.json
  census file digests               rerun-2026-10/serial/census_digests.json (released extraction of the census
                                    serve.log); with QUANTCHECK_CENSUS_SERVELOG pointing at that log (not released)
                                    the script also parses it and asserts that both agree
  October file digests              rerun-2026-10/results*/runs.jsonl
  screen-tuning study (optional)    tuning_p1_humaneval_serial.jsonl in QUANTCHECK_TUNING_DIR (not released). It
                                    feeds only fullrun_table.tuning_full164_separate_study, a summary (counts and
                                    range); without the file that block is copied from the committed facts_b.json
                                    and marked "from_committed_file": true
Writes facts_b.json next to this file (QUANTCHECK_OUT_DIR overrides).
Usage, from the repository root: python3 rerun-2026-10/gate/facts_b.py
"""
import datetime, glob, json, os, re, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))                                   # rerun-2026-10/gate
P2 = os.path.abspath(os.environ.get("QUANTCHECK_ROOT") or os.path.join(HERE, "..", ".."))  # repository root
PR = os.path.abspath(os.environ.get("QUANTCHECK_RERUN_DIR") or os.path.join(P2, "rerun-2026-10"))
SER = os.path.abspath(os.environ.get("QUANTCHECK_SERIAL_DIR") or os.path.join(PR, "serial"))
OUT_DIR = os.path.abspath(os.environ.get("QUANTCHECK_OUT_DIR") or HERE)
DIG = os.path.join(SER, "census_digests.json")
REG = os.path.join(SER, "numbers_regroup.json")
TUNING = os.path.join(os.path.abspath(os.environ.get("QUANTCHECK_TUNING_DIR") or SER), "tuning_p1_humaneval_serial.jsonl")
CENSUS_LOG = os.path.abspath(os.environ.get("QUANTCHECK_CENSUS_SERVELOG")
                             or os.path.join(P2, "results", "pod_archive", "serve.log"))   # not released
COMMITTED = os.path.join(HERE, "facts_b.json")


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


OUT = {}
# ---------------------------------------------------------------- census rows
res_rows = [r for r in jl(os.path.join(P2, "results", "audit_results.jsonl")) if r.get("channel") == "ollama-official"]
assert len(res_rows) == 305 and len({r["tag"] for r in res_rows}) == 305
res = {r["tag"]: r for r in res_rows}
scored = {r["tag"]: r for r in jl(os.path.join(P2, "results", "audit_scored.jsonl")) if r.get("channel") == "ollama-official"}
assert set(scored) == set(res)
TAGS = sorted(res)

# recompute output statistics from per-generation metrics; compare with stored aggregates
stat = {}
for t in TAGS:
    m = res[t]["metrics"]
    assert len(m) == 15, t
    tr = round(sum(1 for x in m if x.get("done_reason") == "length") / len(m), 3)
    rp = round(sum(x["rep6_share"] for x in m) / len(m), 3)
    stat[t] = {"trunc": tr, "rep6": rp}
    assert tr == res[t]["trunc_frac"] == scored[t]["trunc_frac"], t
    assert rp == res[t]["rep6_share_mean"] == scored[t]["rep6_share_mean"], t

# serial 15-task scores
sm = {r["tag"]: r for r in jl(os.path.join(SER, "census_smoke_serial.jsonl")) if r.get("channel") == "ollama-official"}
assert set(sm) == set(TAGS)
score = {}
for t in TAGS:
    pt = sm[t]["per_task"]
    assert len(pt) == 15 and sum(pt.values()) == sm[t]["n_pass"]
    score[t] = sm[t]["n_pass"]
orig_score = {t: scored[t]["smoke_pass"] for t in TAGS}

# ---------------------------------------------------------------- checkpoint grouping, classes
QS = ["q2_K", "q3_K_S", "q3_K_M", "q3_K_L", "q4_0", "q4_K_S", "q4_K_M", "q5_0", "q5_K_S", "q5_K_M", "q6_K", "q8_0", "fp16"]
HIGHQ = {"q6_K", "q8_0", "fp16"}


def split(tag):
    q = max((q for q in QS if tag.endswith("-" + q)), key=len)
    return tag[: -len(q) - 1], q


group = {t: split(t)[0] for t in TAGS}
quant = {t: split(t)[1] for t in TAGS}
members = defaultdict(list)
for t in TAGS:
    members[group[t]].append(t)
assert len(members) == 35


def classify(sc):
    base = {}
    for g, ts in members.items():
        hi = [sc[t] for t in ts if quant[t] in HIGHQ]
        base[g] = statistics.median(hi) if hi else None
    cls = {}
    for t in TAGS:
        b, s = base[group[t]], sc[t]
        if b is None:
            c = "NO_BASELINE"
        elif (s / b if b else 0) >= 0.6:
            c = "HEALTHY"
        elif s <= 2 and b >= 8:
            c = "SUSPECT"
        elif b < 8:
            c = "LOW_BASELINE"
        else:
            c = "DEGRADED"
        cls[t] = c
    return cls, base


cls, base = classify(score)
OUT["classes"] = dict(Counter(cls.values()))
SUS = sorted(t for t in TAGS if cls[t] == "SUSPECT")
assert len(SUS) == 7
reg = json.load(open(REG))
assert set(SUS) == set(reg["classes_serial"]["suspects"])
for k, v in reg["classes_serial"]["per_class"].items():
    kk = "LOW_BASELINE" if k == "COLLAPSED" else k
    assert set(v) == {t for t in TAGS if cls[t] == kk}, k

# ---------------------------------------------------------------- full 164-task evidence
full = {}   # tag -> list of evidence dicts
for r in jl(os.path.join(SER, "census_full164_serial.jsonl")):
    assert len(r["per_task"]) == 164 and sum(r["per_task"].values()) == r["n_pass"]
    full.setdefault(r["tag"], []).append({"source": "census_full164_serial (Aug 2026 census pod, census file)",
                                          "n_pass": r["n_pass"], "old_n_pass": r["old_n_pass"]})
fr_old = {r["tag"]: r["full_pass"] for r in jl(os.path.join(P2, "results", "fullrun_scores.jsonl"))}
assert set(fr_old) == {t for t, e in full.items()}
for t, ev in full.items():
    assert ev[0]["old_n_pass"] == fr_old[t]
for r in jl(os.path.join(PR, "results-v1cases", "scored_serial.jsonl")):
    assert len(r["per_task"]) == 164 and sum(r["per_task"].values()) == r["n_pass"]
    full.setdefault(r["tag"], []).append({"source": "results-v1cases scored_serial (Oct 2026, census file, closure run)",
                                          "n_pass": r["n_pass"], "blob": r["blob"].rsplit("sha256-", 1)[1]})
for fn, lab in (("rerun_r6_serial.jsonl", "R6"), ("rerun_p0c_serial.jsonl", "P0c")):
    for r in jl(os.path.join(SER, fn)):
        if r["id"].startswith("lib-") and r["tag"] in res:
            assert len(r["per_task"]) == 164
            full.setdefault(r["tag"], []).append({"source": f"{lab} October library re-download ({r['id']})",
                                                  "n_pass": r["n_pass"]})
TUNING_AVAILABLE = os.path.exists(TUNING)
if TUNING_AVAILABLE:
    tuning = {}
    for r in jl(TUNING):
        tag = r["tag"].replace("_", ":", 1)
        tuning[tag] = r["n_pass"]

census_full = {t: e[0]["n_pass"] for t, e in full.items() if e[0]["source"].startswith("census_full164")}


def best_full(t):
    """Full-run result on the census-pod / census-file runs (tuning runs excluded)."""
    ev = full.get(t)
    return None if not ev else ev[0]["n_pass"]


def status(t):
    f = best_full(t)
    if f is None:
        return "no full run"
    return "verified at most 16 of 164" if f <= 16 else "verified above 16 of 164"


# ---------------------------------------------------------------- 1) RQ3 output rules
rules = {
    "trunc_ge_0.2": lambda t: stat[t]["trunc"] >= 0.2,
    "rep6_ge_0.2": lambda t: stat[t]["rep6"] >= 0.2,
    "either_ge_0.3": lambda t: stat[t]["trunc"] >= 0.3 or stat[t]["rep6"] >= 0.3,
}
rq3 = {}
for name, f in rules.items():
    hits = sorted(t for t in SUS if f(t))
    extra = sorted(t for t in TAGS if t not in SUS and f(t))
    rows = [{"tag": t, "class": cls[t], "group_baseline": base[group[t]], "serial15": score[t],
             "trunc": stat[t]["trunc"], "rep6_mean": stat[t]["rep6"], "full164_serial": best_full(t),
             "full164_old_pod_score": fr_old.get(t), "status": status(t)} for t in extra]
    rq3[name] = {"suspects_caught": len(hits), "suspects_caught_tags": hits, "extra_flags": len(extra),
                 "extra_of": len(TAGS) - 7, "extra_rows": rows,
                 "status_counts": dict(Counter(r["status"] for r in rows)),
                 "class_counts": dict(Counter(r["class"] for r in rows))}
    rr = reg["rq3_output_rules"][name]
    assert rr["hits"] == len(hits) and rr["false_positives"] == len(extra)
OUT["rq3"] = rq3

# ---------------------------------------------------------------- 2) gate on the census
flag = sorted(t for t in TAGS if score[t] < 9)
flag_orig = sorted(t for t in TAGS if orig_score[t] < 9)
assert len(flag) == 39 and len(flag_orig) == 50
gate = {"stage1_pass": len(TAGS) - len(flag), "stage1_flagged": len(flag), "of": len(TAGS),
        "flagged_by_class": dict(Counter(cls[t] for t in flag)),
        "flagged_original_scorer": len(flag_orig),
        "newly_unflagged": [{"tag": t, "orig15": orig_score[t], "serial15": score[t], "class": cls[t],
                             "full164_serial": best_full(t)} for t in sorted(set(flag_orig) - set(flag))],
        "newly_flagged": sorted(set(flag) - set(flag_orig))}
assert not gate["newly_flagged"]
# unflagged tags by class (classes outside the flag set)
gate["unflagged_by_class"] = dict(Counter(cls[t] for t in TAGS if t not in flag))
# per group
grp = defaultdict(list)
for t in flag:
    if t not in SUS:
        grp[group[t]].append(t)
gate["nonsuspect_flagged_groups"] = []
for g in sorted(grp):
    ts = sorted(grp[g], key=lambda t: QS.index(quant[t]))
    gate["nonsuspect_flagged_groups"].append({
        "group": g, "baseline": base[g], "n_tags_in_group": len(members[g]), "n_flagged": len(ts),
        "tags": [{"quant": quant[t], "class": cls[t], "serial15": score[t], "full164_serial": best_full(t),
                  "status": status(t)} for t in ts]})
ns = [t for t in flag if t not in SUS]
gate["nonsuspect_flagged"] = len(ns)
gate["nonsuspect_flagged_status"] = dict(Counter(status(t) for t in ns))
gate["nonsuspect_flagged_status_by_class"] = {c: dict(Counter(status(t) for t in ns if cls[t] == c))
                                             for c in sorted({cls[t] for t in ns})}
# proposed routing: non-suspect flagged -> full 164 on same file/backend; publish iff >= 17 solved
route = {"publish (>=17 of 164)": sorted(t for t in ns if best_full(t) is not None and best_full(t) >= 17),
         "withhold (<=16 of 164)": sorted(t for t in ns if best_full(t) is not None and best_full(t) <= 16),
         "pending (full run needed)": sorted(t for t in ns if best_full(t) is None)}
gate["routing_rule_text"] = ("A flagged tag that is not a suspect, whatever its class, goes to a full 164-task run on the "
                             "same file and backend and is published only if it solves at least 17 tasks (the run can stop "
                             "once 17 distinct tasks pass); otherwise it is withheld.")
narrow = [t for t in ns if cls[t] in ("NO_BASELINE", "LOW_BASELINE")]
gate["narrow_variant_no_or_low_baseline_only"] = {
    "routed": len(narrow),
    "publish": sorted(t for t in narrow if best_full(t) is not None and best_full(t) >= 17),
    "withhold": sorted(t for t in narrow if best_full(t) is not None and best_full(t) <= 16),
    "published_by_class_although_verified_le16": sorted(f"{t} ({cls[t]}, {best_full(t)}/164)" for t in ns
                                                        if t not in narrow and best_full(t) is not None and best_full(t) <= 16)}
gate["routing_rule_on_census"] = {k: {"n": len(v), "tags": [f"{t} ({score[t]}/15" + (f", {best_full(t)}/164)" if best_full(t) is not None else ")") for t in v]}
                                  for k, v in route.items()}
# calibrated rebuilds against the screen (stage one >= 9 of 15) and their full-run scores
R1 = reg["R1"]; R5 = reg["R5"]; P0 = reg["P0_smoke"]; F = reg["full164"]
cal = []
for lvl in ("Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L"):
    cal.append({"build": f"own WikiText imatrix Qwen-3B {lvl}", "s15": R5[f"cal-qwen3b-{lvl}"], "f164": F["own_imatrix_wikitext"][lvl]})
    cal.append({"build": f"own code imatrix Qwen-3B {lvl}", "s15": P0[f"codeimat-qwen3b-{lvl}"], "f164": F["own_imatrix_code"][lvl]})
    cal.append({"build": f"bartowski imatrix Qwen-3B {lvl}", "s15": R1[f"imat-qwen3b-{lvl}"], "f164": F["bartowski_qwen"][lvl]})
cal.append({"build": "own WikiText imatrix phi3.5 Q2_K (current mix)", "s15": R5["cal-phi35-Q2_K"], "f164": F["phi35"]["wikitext_imatrix_cal"]})
cal.append({"build": "own code imatrix phi3.5 Q2_K (current mix)", "s15": P0["codeimat-phi35-Q2_K"], "f164": None})
cal.append({"build": "bartowski imatrix phi3.5 Q2_K", "s15": R1["imat-phi35-Q2_K"], "f164": F["phi35"]["bartowski"]})
cal.append({"build": "Qwen AWQ GGUF q2_k", "s15": R1["awq-qwen3b-q2_k"], "f164": F["awq_qwen"]["q2_K"]})
cal.append({"build": "Qwen AWQ GGUF q3_k_m", "s15": R1["awq-qwen3b-q3_k_m"], "f164": F["awq_qwen"]["q3_K_M"]})
for c in cal:
    c["clears_screen_ge9"] = c["s15"] >= 9
gate["calibrated_builds_vs_screen"] = cal
OUT["gate"] = gate

# ---------------------------------------------------------------- 3) persistence of the seven suspects
rel = json.load(open(DIG))["artifacts"]
if os.path.exists(CENSUS_LOG):      # own parse of the census serve.log, checked against census_digests.json
    TS = re.compile(r"^time=(\S+) ")
    LOADRE = re.compile(r'msg="using llama-server for model" model=\S*/blobs/sha256-([0-9a-f]{64})')
    loads = []
    for line in open(CENSUS_LOG, errors="replace"):
        m = LOADRE.search(line)
        if m:
            ts = datetime.datetime.fromisoformat(TS.match(line).group(1).replace("Z", "+00:00")).timestamp()
            loads.append((ts, m.group(1)))
    own_dig = {}
    for t in TAGS:
        a, b = res[t]["ts_start"] - 1, res[t]["ts_end"] + 1
        w = {h for ts, h in loads if a <= ts <= b}
        assert len(w) == 1, (t, w)
        own_dig[t] = w.pop()
    assert all(own_dig[t] == rel[t]["blob_sha256"] for t in TAGS)
    DIGEST_SOURCE = "census serve.log (own parse), equal to census_digests.json for all 305 official tags"
else:                               # released extraction of the same log (rerun-2026-10/serial/census_digests.py)
    own_dig = {t: rel[t]["blob_sha256"] for t in TAGS}
    DIGEST_SOURCE = "census_digests.json (the census serve.log is not released)"
octo = defaultdict(list)
for f in sorted(glob.glob(os.path.join(PR, "results*", "runs.jsonl"))):
    for r in jl(f):
        if r.get("kind") != "ollama" or r.get("tag") not in res:
            continue
        blob = (r.get("blob") or "").rsplit("sha256-", 1)[-1] or None
        fh = (r.get("hash") or {}).get("file_sha256")
        octo[r["tag"]].append({"dir": os.path.basename(os.path.dirname(f)), "id": r["id"], "setting": r.get("setting"),
                               "pull_s": r.get("pull_s"), "blob": blob, "file_sha256": fh, "error": r.get("error")})
pers = {}
for t in SUS:
    rows = octo.get(t, [])
    ok_rows = [x for x in rows if x["blob"]]
    pers[t] = {"census_digest": own_dig[t], "october_runs": len(rows),
               "october_pulls_recorded": sum(1 for x in rows if x["pull_s"] is not None),
               "october_distinct_blobs": sorted({x["blob"] for x in ok_rows}),
               "october_file_sha256_computed": sorted({x["file_sha256"] for x in ok_rows if x["file_sha256"]}),
               "all_blobs_equal_census": bool(ok_rows) and all(x["blob"] == own_dig[t] for x in ok_rows),
               "file_hash_equals_census": bool([x for x in ok_rows if x["file_sha256"]]) and all(
                   x["file_sha256"] == own_dig[t] for x in ok_rows if x["file_sha256"]),
               "dirs": dict(Counter(x["dir"] for x in rows))}
OUT["persistence"] = pers
# every official tag re-run in October: digest equality
oct_all = {t: {"n_runs": len(v), "equal": all(x["blob"] == own_dig[t] for x in v if x["blob"]),
               "blobs": sorted({x["blob"][:12] for x in v if x["blob"]}), "census": own_dig[t][:12]}
           for t, v in octo.items()}
OUT["october_official_tags"] = {"n_tags": len(oct_all), "n_equal": sum(1 for v in oct_all.values() if v["equal"]),
                                "not_equal": {t: v for t, v in oct_all.items() if not v["equal"]}}

# ---------------------------------------------------------------- 4) rep6_share
gens = [(t, x["task_id"], x["rep6_share"], x.get("out_words")) for t in TAGS for x in res[t]["metrics"]]
mx = max(gens, key=lambda g: g[2])
all_rows = jl(os.path.join(P2, "results", "audit_results.jsonl"))
gens_all = [(r["tag"], x["task_id"], x["rep6_share"]) for r in all_rows for x in (r.get("metrics") or [])]
OUT["rep6"] = {
    "formula": "toks = output.split(); if len(toks) >= 12: rep6_share = round(6 * max_count(overlapping word 6-grams) / len(toks), 3) else 0.0; artifact statistic = mean over the 15 generations (rep6_share_mean)",
    "upper_bound": "6 * (n - 5) / n < 6 (one word repeated n times); a period-p loop with p <= 6 gives about 6/p",
    "official_generations": len(gens),
    "max_generation": {"tag": mx[0], "task": mx[1], "rep6_share": mx[2], "out_words": mx[3]},
    "generations_gt_1": sum(1 for g in gens if g[2] > 1),
    "artifacts_with_any_generation_gt_1": dict(Counter(g[0] for g in gens if g[2] > 1)),
    "max_artifact_mean": max((stat[t]["rep6"], t) for t in TAGS),
    "artifacts_mean_gt_1": sorted((t, stat[t]["rep6"]) for t in TAGS if stat[t]["rep6"] > 1),
    "max_generation_all_census_rows": max(g[2] for g in gens_all),
    "suspect_means": {t: stat[t]["rep6"] for t in SUS},
    "healthy_median_mean": statistics.median(stat[t]["rep6"] for t in TAGS if cls[t] == "HEALTHY"),
}

# ---------------------------------------------------------------- 5) full-run table (non-suspects)
tab = []
for t in sorted(full):
    if t in SUS:
        continue
    for e in full[t]:
        tab.append({"tag": t, "class": cls[t], "serial15": score[t], "orig15": orig_score[t],
                    "stage1_flag_serial": score[t] < 9, "stage1_flag_original": orig_score[t] < 9,
                    "full164_serial": e["n_pass"], "source": e["source"]})
census_ns = [x for x in tab if x["source"].startswith("census_full164")]
# screen-tuning study: summary only (per-configuration and per-task results belong to a separate study, withheld)
if TUNING_AVAILABLE:
    ns_tun = [v for t, v in tuning.items() if t in res and t not in SUS]
    tun_block = {"n": len(tuning), "not_in_census": sorted(t for t in tuning if t not in res),
                 "n_nonsuspect_in_census": len(ns_tun), "nonsuspect_in_census_full164_range": [min(ns_tun), max(ns_tun)],
                 "n_suspect_in_census": sum(1 for t in tuning if t in SUS),
                 "note": ("full 164-task runs of the 24 screen-tuning configurations, from a separate study; file identity "
                          "with the census not recorded; per-configuration and per-task results are not released"),
                 "from_committed_file": False}
else:
    tun_block = dict(json.load(open(COMMITTED))["fullrun_table"]["tuning_full164_separate_study"])
    tun_block["from_committed_file"] = True
OUT["fullrun_table"] = {
    "census_full164_rows": len(full and [t for t in full if full[t][0]["source"].startswith("census_full164")]),
    "census_full164_nonsuspect": len(census_ns),
    "census_nonsuspect_above_16": sorted((x["tag"], x["full164_serial"]) for x in census_ns if x["full164_serial"] > 16),
    "census_nonsuspect_at_most_16": sorted((x["tag"], x["full164_serial"]) for x in census_ns if x["full164_serial"] <= 16),
    "other_full_runs_nonsuspect": [x for x in tab if not x["source"].startswith("census_full164")],
    "rows": tab,
    "tuning_full164_separate_study": tun_block,
}
OUT["fullrun_table"]["census_selection_rule"] = (
    "harness/fullrun.py: every official tag with original smoke_pass <= 2 and verdict DEFECTIVE (13), plus the "
    "lowest-scoring tag with original smoke_pass 3..8 per (model, size) key (14; the gemma3 270m tags fail the size "
    "regex, so each is its own key); rule-based, not random")
r16 = [x for x in census_ns if x["full164_serial"] > 16]
OUT["fullrun_table"]["census_nonsuspect_above_16_range"] = [min(x["full164_serial"] for x in r16), max(x["full164_serial"] for x in r16)]
OUT["fullrun_table"]["newly_unflagged_with_full_run"] = [(x["tag"], x["full164_serial"]) for x in tab
                                                          if x["stage1_flag_original"] and not x["stage1_flag_serial"]]

json.dump(OUT, open(os.path.join(OUT_DIR, "facts_b.json"), "w"), indent=1, default=str)
print(json.dumps({k: OUT[k] for k in ("classes",)}, indent=0))
print("census digests from:", DIGEST_SOURCE)
print("tuning summary:", "recomputed from " + os.path.basename(TUNING) if TUNING_AVAILABLE
      else "copied from the committed facts_b.json (tuning file not released)")
