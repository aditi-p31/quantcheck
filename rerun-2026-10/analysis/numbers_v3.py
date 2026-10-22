#!/usr/bin/env python3
"""Every number the revised paper (v3: TrustAI-BD submission and arXiv v2) cites, from the raw data.

Inputs: the census (results/audit_*.jsonl, fullrun_scores.jsonl), the executed census rescore
(census_rescore.jsonl), and the 2026-10 rerun results (pod-results/results-*). Classification reuses
analysis/analyze.py unchanged; the only difference from the published census is the corrected score.
Writes numbers_v3.json next to this file and prints a summary.
"""
import importlib.util, json, os, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.abspath(os.path.join(HERE, "..", ".."))
# Paths are configurable; defaults follow the repository layout (this file is rerun-2026-10/analysis/numbers_v3.py).
RERUN = os.environ.get("QUANTCHECK_RERUN_DIR", os.path.abspath(os.path.join(HERE, "..")))
SUITE = json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"]

spec = importlib.util.spec_from_file_location("analyze", os.path.join(P2, "analysis", "analyze.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def latest(path, key=("id", "setting")):
    """Last record per key (reruns append)."""
    out = {}
    for r in jl(path):
        out[tuple(r[k] for k in key)] = r
    return out


def wilson(k, n):
    p, lo, hi = A.wilson(k, n)
    return {"k": k, "n": n, "rate": round(p, 4), "lo": round(lo, 4), "hi": round(hi, 4)}


N = {}
scored = jl(os.path.join(P2, "results", "audit_scored.jsonl"))
official = [r for r in scored if r.get("channel") == "ollama-official"]
community = [r for r in scored if r.get("channel") == "hf-community"]
fullruns = {r["tag"]: r for r in jl(os.path.join(P2, "results", "fullrun_scores.jsonl"))}
rescore = {r["tag"]: r for r in jl(os.path.join(RERUN, "census_rescore.jsonl"))}

N["census"] = {
    "official": len(official), "community": len(community),
    "official_fp16": sum(1 for r in official if "fp16" in r["tag"]),
    "lines": len({A.norm_model(r["tag"]) for r in official}),
    "family_groups": None,
}
N["census"]["official_quantized"] = N["census"]["official"] - N["census"]["official_fp16"]


def reg_group(tag):
    """(registry model line, size) from the tag itself; analyze.size_key merges gemma3's 270m size."""
    import re
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
    pt = rescore[r["tag"]]["per_task"]
    return sum(1 for t in SUITE if pt.get(t))


for name, fn in (("original", orig), ("rescored", fixed)):
    cls, base = classify(official, fn)
    N[f"classes_{name}"] = dict(Counter(cls.values()))
    N[f"stage1_flags_{name}"] = sum(1 for r in official if fn(r) < 9)
    N[f"suspects_{name}"] = sorted(t for t, c in cls.items() if c == "SUSPECT")
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

# Community channel
N["community_healthy_cuda"] = sum(1 for r in community if r["smoke_pass"] >= 9)

# Rerun results
def tab(dirname, setting=None):
    p = os.path.join(RERUN, dirname, "scored.jsonl")
    out = {}
    for (i, s), r in latest(p).items():
        if setting is None or s == setting:
            out[i if setting else (i, s)] = r["n_pass"]
    return out

N["R1"] = tab("results", "base")
N["R2"] = {f"{i}|{s}": v for (i, s), v in tab("results-r2").items()}
N["R5"] = tab("results-r5", "base")
N["R6"] = tab("results-r6", "full164")
N["P0_smoke"] = tab("results-p0", "base")
N["P0c"] = tab("results-p0c", "full164")
N["G1"] = tab("results-g1", "base")

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
    import re
    m = re.findall(r"Final estimate: PPL = ([0-9.]+)", t)
    if m:
        ppl[f[:-4]] = float(m[-1])
N["ppl"] = ppl

# Tensor identity
N["tensor_identity"] = [ {k: r[k] for k in ("a", "b", "n_tensors", "identical_tensors", "type_differs", "same_type_bytes_differ")}
                         for f in ("p0b_tensor_compare.jsonl", "p0f_compare.jsonl", "g1_tensor_compare.jsonl")
                         for r in jl(os.path.join(RERUN, f))]

# Suite robustness (A1)
a1 = json.load(open(os.path.join(os.environ.get("QUANTCHECK_A1_DIR", os.path.join(RERUN, "a1")), "a1_results.json")))
N["A1_keys"] = sorted(a1.keys())[:30]

out = os.path.join(HERE, "numbers_v3.json")
json.dump(N, open(out, "w"), indent=1, default=str)
for k in ("census", "classes_original", "classes_rescored", "stage1_flags_original", "stage1_flags_rescored",
          "he15_pass_rescored", "artifacts_changed_by_rescore", "suspects", "nonfunctional", "nonfunctional_groups",
          "nonfunctional_incidents", "lowbit_le4b", "screen_seconds", "community_healthy_cuda", "fn_audit"):
    print(k, json.dumps(N[k], default=str))
print("R6", N["R6"]); print("P0c", N["P0c"]); print("ppl", N["ppl"]); print("A1 keys", N["A1_keys"])
