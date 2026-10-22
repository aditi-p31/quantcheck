#!/usr/bin/env python3
"""Population bounds for the RQ4 miss audit, with every assumption named per row.

Independent of certificates.py: rebuilds the sampling frame, the strata and the three samples from the
raw census scores, the inventory and the sampling manifests, checks the outcomes against the serial
scores, the run records and the census digests, and computes each bound by exact test inversion.

Event: a tag's August census file is non-functional (solves at most 16 of the 164 HumanEval+ tasks
under the census settings). Bound: the largest total number of such tags D = sum_h D_h for which the
probability of the observed sample outcome, a product of per-stratum hypergeometric terms, is at least
0.05. Observed outcome per stratum: zero failures, P(X_h = 0 | D_h); for a stratum that holds the
re-published gemma3:4b-it-q8_0 when its August file is treated as possibly failed, P(X_h <= 1 | D_h).

Read-only on every input. Writes bounds.csv and bounds.json next to this file (QUANTCHECK_OUT_DIR
overrides). Stdlib only. Usage, from the repository root: python3 rerun-2026-10/miss_audit/bounds.py

Inputs (all in this release; defaults follow the repository layout, and QUANTCHECK_ROOT,
QUANTCHECK_RERUN_DIR and QUANTCHECK_SERIAL_DIR override them):
  results/audit_scored.jsonl, inventory_candidates.json, sensitivity_sample.json   (repository root)
  rerun-2026-10/fn_sample_30.json, fn_sample_b.json                                 (the two seeded manifests)
  rerun-2026-10/serial/tuning_configs.json        names of the 24 screen-tuning configurations (excluded
                                                  from the frame; their per-task results are not needed)
  rerun-2026-10/serial/{sensitivity,rerun_r3,rerun_r3b,census_smoke}_serial.jsonl, census_digests.json
  rerun-2026-10/results-r3/runs.jsonl, results-r3b/runs.jsonl, results-v1cases/scored_serial.jsonl
"""
import csv, json, math, os, random
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))                                   # rerun-2026-10/miss_audit
P2 = os.path.abspath(os.environ.get("QUANTCHECK_ROOT") or os.path.join(HERE, "..", ".."))  # repository root
POD = os.path.abspath(os.environ.get("QUANTCHECK_RERUN_DIR") or os.path.join(P2, "rerun-2026-10"))
SER = os.path.abspath(os.environ.get("QUANTCHECK_SERIAL_DIR") or os.path.join(POD, "serial"))
OUT_DIR = os.path.abspath(os.environ.get("QUANTCHECK_OUT_DIR") or HERE)
RUNF = POD                                                                          # fn_sample_*.json
DIGESTS = os.path.join(SER, "census_digests.json")
ALPHA = 0.05
GEMMA = "gemma3:4b-it-q8_0"


def jl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]


# ------------------------------------------------------------------ frame and strata
scored = {r["tag"]: r for r in jl(os.path.join(P2, "results", "audit_scored.jsonl"))}
inv = {a["tag"]: a for a in json.load(open(os.path.join(P2, "inventory_candidates.json")))["artifacts"]}
tuning = {i.replace("_", ":", 1) for i in json.load(open(os.path.join(SER, "tuning_configs.json")))["ids"]}
official = [t for t, r in scored.items() if r["channel"] == "ollama-official"]
frame = [t for t in official if scored[t]["smoke_pass"] >= 9 and t not in tuning]
fam = lambda t: scored[t]["family"]
N233 = Counter(fam(t) for t in frame)
assert len(frame) == 233

v1 = [a["tag"] for a in json.load(open(os.path.join(P2, "sensitivity_sample.json")))["artifacts"]]
mA = json.load(open(os.path.join(RUNF, "fn_sample_30.json")))
mB = json.load(open(os.path.join(RUNF, "fn_sample_b.json")))
rA = [a["tag"] for a in mA["artifacts"]]
rB = [a["tag"] for a in mB["artifacts"]]
assert set(v1) <= set(frame) and len(set(v1 + rA + rB)) == 66
f223 = [t for t in frame if t not in v1]
f194 = [t for t in f223 if t not in rA]
assert len(f223) == mA["frame_size"] == 223 and len(f194) == mB["frame_size"] == 194
assert set(rA) <= set(f223) and set(rB) <= set(f194)


def seeded_draw(pool, seed, per):
    """Candidate procedure: families in sorted order, rng.sample over the sorted family pool."""
    rng = random.Random(seed)
    out = []
    for f in sorted({fam(t) for t in pool}):
        p = sorted(t for t in pool if fam(t) == f)
        out += rng.sample(p, min(per, len(p)))
    return out


draw_reproduced = {"fn_sample_30": seeded_draw(f223, mA["seed"], mA["per_family"]) == rA,
                   "fn_sample_b": seeded_draw(f194, mB["seed"], mB["per_family"]) == rB}

N223 = Counter(fam(t) for t in f223)
n66 = Counter(fam(t) for t in v1 + rA + rB)
n56 = Counter(fam(t) for t in rA + rB)
nv1 = Counter(fam(t) for t in v1)
STRATA = sorted(N233)
GSTRAT = fam(GEMMA)
assert GEMMA in rA

# ------------------------------------------------------------------ outcomes (serial scores, run records)
aud = {}
for name in ("sensitivity_serial.jsonl", "rerun_r3_serial.jsonl", "rerun_r3b_serial.jsonl"):
    for r in jl(os.path.join(SER, name)):
        tag = r["tag"] if ":" in r["tag"] else r["tag"].replace("_", ":", 1)
        aud[tag] = sum(1 for v in r["per_task"].values() if v)
        assert len(r["per_task"]) == 49
assert set(aud) == set(v1 + rA + rB)
closure = {r["tag"]: (r["n_pass"], r["n"], r["blob"].split("sha256-")[-1])
           for r in jl(os.path.join(POD, "results-v1cases", "scored_serial.jsonl"))}
cdig = {t: a["blob_sha256"] for t, a in json.load(open(DIGESTS))["artifacts"].items() if "blob_sha256" in a}
octblob = {}
for d in ("results-r3", "results-r3b"):
    for r in jl(os.path.join(POD, d, "runs.jsonl")):
        if "blob" in r:                       # one r3 record is a failed pull (HTTP 503), retried later
            octblob[r["tag"]] = r["blob"].split("sha256-")[-1]
assert set(rA + rB) <= set(octblob)
digest_mismatch = sorted(t for t in rA + rB if octblob[t] != cdig[t])
closure_on_census = {t: (c[0], c[1], c[2] == cdig[t]) for t, c in closure.items()}
v1_closed = set(closure)
v1_open = [t for t in v1 if t not in v1_closed]

# ------------------------------------------------------------------ v1 randomization diagnostic
size = {t: inv[t]["file_size_gb"] for t in frame}
vmax = max(size[t] for t in v1)
p_strat = 1.0
for h in STRATA:
    k = nv1.get(h, 0)
    small = sum(1 for t in frame if fam(t) == h and size[t] <= vmax)
    p_strat *= math.comb(small, k) / math.comb(N233[h], k)
small_all = sum(1 for t in frame if size[t] <= vmax)
p_srs = math.comb(small_all, 10) / math.comb(233, 10)


# ------------------------------------------------------------------ exact stratified test inversion
def logp(N, n, D, k):
    """log P(X <= k) for X ~ Hypergeometric(N, D, n); -inf when impossible."""
    s = sum(math.comb(D, x) * math.comb(N - D, n - x) for x in range(0, k + 1))
    return math.log(s / math.comb(N, n)) if s > 0 else float("-inf")


def strat_bound(Ns, ns, adverse=None, alpha=ALPHA):
    """Max sum D_h with prod_h P(X_h <= k_h | D_h) >= alpha; k_h = 1 for `adverse`, else 0.
    Returns (bound, allocation, prob at bound, best prob at bound + 1)."""
    keys = [h for h in sorted(Ns) if ns.get(h, 0) > 0 or Ns[h] > 0]
    best = {0: (0.0, {})}
    for h in keys:
        N, n, k = Ns[h], ns.get(h, 0), (1 if h == adverse else 0)
        terms = [(d, logp(N, n, d, k)) for d in range(0, N + 1)]
        nxt = {}
        for tot, (lp, alloc) in best.items():
            for d, l in terms:
                v = lp + l
                if v == float("-inf"):
                    continue
                if tot + d not in nxt or v > nxt[tot + d][0]:
                    a = dict(alloc)
                    if d:
                        a[h] = d
                    nxt[tot + d] = (v, a)
        best = nxt
    ok = [t for t, (lp, _) in best.items() if lp >= math.log(alpha) - 1e-15]
    D = max(ok)
    above = best.get(D + 1, (float("-inf"), None))[0]
    return D, best[D][1], math.exp(best[D][0]), (math.exp(above) if above > float("-inf") else 0.0)


def wilson_hi(k, n, z=1.959963984540054):
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def srs_bound(N, n, alpha=ALPHA):
    D = 0
    while D + 1 <= N - n and math.comb(N - D - 1, n) / math.comb(N, n) >= alpha:
        D += 1
    return D


POP233 = "233 unflagged official tags outside the tuning set, as scored and served at the August census"
POP223 = "223 of those 233 not in the first-version sample of 10"
EVENT = "census file non-functional (solves at most 16 of the 164 HumanEval+ tasks)"
SRS_LATER = ("two later rounds are simple random within strata from the 223 (seeds 20261021/20261022; "
             "both draws reproduced exactly from the seeds)")
SRS_ALL = ("all 66 are simple random within strata from the 233, including the first-version 10, "
           "whose draw procedure is unrecorded and whose file sizes (all <= 3.9 GB) are unlikely under that "
           "design (p = 0.003, post hoc)")
ID_V1 = "the 8 first-version audit-alone runs loaded the census files (run digest and backend unrecorded)"
ID_GEMMA_PASS = f"the October {GEMMA} file (34/49) stands in for the August census file"
GEMMA_ADV = f"August {GEMMA} file allowed to have failed (stratum factor P(X<=1))"

rows = []


def add(rid, pop, popN, sample, assumptions, b, extra_D=0, review=None, note=""):
    D, alloc, pr, pr1 = b
    tot = D + extra_D
    rows.append({
        "row": rid, "population": pop, "population_size": popN, "event": EVENT,
        "sample_used_for_inference": sample, "assumptions": assumptions,
        "upper_count": tot, "upper_share_pct": round(100 * tot / popN, 1),
        "stratified_part": D, "deterministic_worst_case_added": extra_D,
        "worst_allocation": json.dumps(alloc, sort_keys=True),
        "non_rejection_prob_at_bound": round(pr, 6), "max_prob_at_bound_plus_1": round(pr1, 6),
        "review_value": review, "matches_review": (review == f"{tot}/{popN}") if review else None,
        "note": note})


b1 = strat_bound(N233, n66)
b2 = strat_bound(N233, n66, adverse=GSTRAT)
b3 = strat_bound(N223, n56)
b4 = strat_bound(N223, n56, adverse=GSTRAT)
add("1", POP233, 233, "66 draws (10 first-version + 56 seeded)", "; ".join([SRS_ALL, ID_V1, ID_GEMMA_PASS]),
    b1, review="15/233")
add("2", POP233, 233, "66 draws", "; ".join([SRS_ALL, ID_V1, GEMMA_ADV]), b2, review="17/233")
add("3", POP223, 223, "56 seeded draws", "; ".join([SRS_LATER, ID_GEMMA_PASS]), b3, review="20/223")
add("4", POP223, 223, "56 seeded draws", "; ".join([SRS_LATER, GEMMA_ADV]), b4, review="22/223",
    note="the bound the paper prints")
add("5", POP233, 233, "56 seeded draws; first-version 10 handled deterministically",
    "; ".join([SRS_LATER, GEMMA_ADV,
               "no assumption about the first-version 10: the 8 without a file record count as possible failures; "
               "the 2 rerun on all 164 tasks on the census digest (65 and 44 of 164) count as observed passes"]),
    b4, extra_D=len(v1_open), review="30/233", note="assumption-free about the first-version sample")
add("4b", POP233, 233, "56 seeded draws; first-version 10 taken as observed passes, not as random draws",
    "; ".join([SRS_LATER, GEMMA_ADV, ID_V1]), b4, extra_D=0,
    note="supplementary: identity assumption for 8 legacy runs, no randomness assumption")

supp = {
    "wilson_upper_0_of_66_pct": round(100 * wilson_hi(0, 66), 2),
    "wilson_upper_0_of_56_pct": round(100 * wilson_hi(0, 56), 2),
    "srs_hypergeometric_0_of_66_in_233": srs_bound(233, 66),
}

out = {
    "inputs": {
        "census_scores": "results/audit_scored.jsonl", "inventory": "inventory_candidates.json",
        "tuning": "rerun-2026-10/serial/tuning_configs.json",
        "v1_sample": "sensitivity_sample.json",
        "round_samples": ["rerun-2026-10/fn_sample_30.json", "rerun-2026-10/fn_sample_b.json"],
        "audit_scores": ["rerun-2026-10/serial/sensitivity_serial.jsonl", "rerun-2026-10/serial/rerun_r3_serial.jsonl",
                         "rerun-2026-10/serial/rerun_r3b_serial.jsonl"],
        "closure": "rerun-2026-10/results-v1cases/scored_serial.jsonl",
        "digests": ["rerun-2026-10/serial/census_digests.json", "rerun-2026-10/results-r3/runs.jsonl",
                    "rerun-2026-10/results-r3b/runs.jsonl"],
        "screen_serial": "rerun-2026-10/serial/census_smoke_serial.jsonl",
    },
    "frame": {"official": len(official), "frame_233": len(frame), "frame_223": len(f223), "frame_194": len(f194)},
    "strata": {h: {"N_233": N233[h], "n_66": n66.get(h, 0), "n_v1": nv1.get(h, 0),
                   "N_223": N223[h], "n_56": n56.get(h, 0)} for h in STRATA},
    "seeded_draws_reproduced": draw_reproduced,
    "seeded_draw_procedure": ("random.Random(seed); for each family group in sorted order, "
                              "rng.sample(sorted(frame tags in that group), min(3, size)); frame = official tags "
                              "with original 15-task score >= 9, minus the 23 tuning configs in the census, minus "
                              "the first-version 10 (and, for round two, minus round one)"),
    "outcomes": {"audit_min_of_49": min(aud.values()), "audit_max_of_49": max(aud.values()),
                 "audit_at_or_below_2": sum(1 for v in aud.values() if v <= 2),
                 "closure_full164_on_census_digest": closure_on_census,
                 "first_version_without_file_record": v1_open,
                 "october_digest_differs_from_census": digest_mismatch,
                 "gemma_digests": {"census": cdig[GEMMA], "october": octblob[GEMMA], "october_49": aud[GEMMA],
                                   "census_screen_15_original_scorer": scored[GEMMA]["smoke_pass"],
                                   "census_screen_15_serial": next(
                                       sum(1 for v in r["per_task"].values() if v)
                                       for r in jl(os.path.join(SER, "census_smoke_serial.jsonl"))
                                       if r["tag"] == GEMMA)}},
    "v1_randomization_diagnostic": {
        "v1_max_file_gb": vmax, "frame_tags_at_or_below": small_all,
        "p_all_10_at_or_below_given_within_stratum_srs_with_v1_allocation": p_strat,
        "p_all_10_at_or_below_given_srs_10_of_233": p_srs,
        "v1_allocation": {h: nv1.get(h, 0) for h in STRATA},
        "caveat": "size cut-off read off the sample (post hoc); a diagnostic, not a pre-planned test"},
    "rows": rows,
    "supplementary": supp,
}
json.dump(out, open(os.path.join(OUT_DIR, "bounds.json"), "w"), indent=1)
cols = ["row", "population", "population_size", "event", "sample_used_for_inference", "assumptions",
        "upper_count", "upper_share_pct", "stratified_part", "deterministic_worst_case_added",
        "worst_allocation", "non_rejection_prob_at_bound", "max_prob_at_bound_plus_1", "review_value",
        "matches_review", "note"]
with open(os.path.join(OUT_DIR, "bounds.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)

print(json.dumps({k: out[k] for k in ("frame", "seeded_draws_reproduced", "outcomes",
                                       "v1_randomization_diagnostic", "supplementary")}, indent=1))
for h, s in out["strata"].items():
    print(f"{h:40s} {s}")
for r in rows:
    print(r["row"], f'{r["upper_count"]}/{r["population_size"]} ({r["upper_share_pct"]}%)', r["worst_allocation"],
          r["non_rejection_prob_at_bound"], r["max_prob_at_bound_plus_1"], r["review_value"], r["matches_review"])
