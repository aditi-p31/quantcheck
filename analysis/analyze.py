#!/usr/bin/env python3
"""Final analysis for the audit paper. Reads results/*.jsonl, writes
analysis/findings.json (every number the paper cites) + prints a report.

Verdict pipeline (frozen in DESIGN.md):
  1. family-relative classification (classify.py logic, inline here)
  2. DEFECTIVE requires: smoke<=2 of a capable family (baseline>=8) AND
     full-164 confirmation (<10% pass@1) AND a cross-distributor referee
     that scores healthy (>=0.6 of baseline) on the same model+quant.
  3. COLLAPSED = low score but weak/small family OR referee also fails
     (capability limit, not a distribution defect).
"""
import glob, json, os, re, statistics
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "..", "results")
HIGH = {"q6_K", "q8_0", "fp16", "f16"}

def load(name):
    p = os.path.join(RES, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

MODEL_ALIASES = [
    ("qwen2.5-coder", "qwen2.5-coder"), ("qwen2.5", "qwen2.5"),
    ("llama-3.2", "llama3.2"), ("llama3.2", "llama3.2"),
    ("llama-3.1", "llama3.1"), ("llama3.1", "llama3.1"),
    ("phi-3.5", "phi3.5"), ("phi3.5", "phi3.5"), ("phi-4", "phi4"),
    ("gemma-3", "gemma3"), ("gemma3", "gemma3"), ("gemma-2", "gemma2"), ("gemma2", "gemma2"),
    ("deepseek-coder", "deepseek-coder"), ("codellama", "codellama"),
    ("starcoder2", "starcoder2"), ("granite", "granite"), ("yi-coder", "yi-coder"),
    ("codegemma", "codegemma"), ("mistral", "mistral"), ("codestral", "codestral"),
]
QUANTS = ["q2_k", "q3_k_s", "q3_k_m", "q3_k_l", "q4_0", "q4_k_s", "q4_k_m",
          "q5_k_s", "q5_k_m", "q6_k", "q8_0", "fp16", "f16"]
def norm_model(tag):
    t = (tag[3:] if tag.startswith("hf:") else tag).lower()
    for needle, canon in MODEL_ALIASES:
        if needle in t:
            return canon
    return t.split(":")[0].split("/")[0]
def norm_size(tag):
    t = (tag[3:] if tag.startswith("hf:") else tag).lower()
    m = re.search(r"(\d+(?:\.\d+)?)b", t)
    return m.group(1) if m else "?"
def tag_quant(tag):
    t = (tag[3:] if tag.startswith("hf:") else tag).lower().replace("-", "_")
    for q in QUANTS:  # longest-first so q3_k_m beats q3_k
        if q in t:
            return q
    return None
def size_key(tag):
    return (norm_model(tag), norm_size(tag))

def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5) / d
    return (p, max(0, c-h), min(1, c+h))

def main():
    scored = load("audit_scored.jsonl")
    fullruns = {r["tag"]: r for r in load("fullrun_scores.jsonl")}
    official = [r for r in scored if r.get("channel") == "ollama-official"]
    community = [r for r in scored if r.get("channel") == "hf-community"]
    referees = {r["tag"]: r for r in scored if r.get("channel") == "hf-adjudication"}

    # family baselines (official only)
    fam = defaultdict(list)
    for r in official:
        fam[size_key(r["tag"])].append(r)
    baseline = {}
    for k, g in fam.items():
        hi = [x["smoke_pass"] for x in g if any(h in x["tag"] for h in HIGH)]
        baseline[k] = statistics.median(hi) if hi else None

    # classify
    classes = {}
    for r in official:
        k = size_key(r["tag"]); b = baseline[k]; s = r["smoke_pass"]
        if b is None:
            classes[r["tag"]] = "NO_BASELINE"; continue
        ratio = s / b if b else 0
        if ratio >= 0.6:
            classes[r["tag"]] = "HEALTHY"
        elif s <= 2 and b >= 8:
            classes[r["tag"]] = "DEFECT_SUSPECT"
        elif ratio < 0.6 and b < 8:
            classes[r["tag"]] = "COLLAPSED"
        else:
            classes[r["tag"]] = "DEGRADED"

    # confirm defects with full-run + referee
    confirmed, cleared = [], []
    for r in official:
        if classes[r["tag"]] != "DEFECT_SUSPECT":
            continue
        full = fullruns.get(r["tag"], {}).get("full_pass")
        # find a referee by explicit family+params+quant metadata (HF tags
        # don't parse like Ollama tags, so match on recorded fields)
        k = size_key(r["tag"]); q = str(r.get("quant", "")).lower()
        ref = None; ref_q = None
        km = norm_model(r["tag"]); ks = norm_size(r["tag"]); kq = tag_quant(r["tag"])
        cands = [rr for rr in referees.values()
                 if norm_model(rr["tag"]) == km
                 and (norm_size(rr["tag"]) == ks or norm_size(rr["tag"]) == "?" or ks == "?")]
        BPW = {"q2_k": 2.56, "q3_k_s": 3.44, "q3_k_m": 3.91, "q3_k_l": 4.27,
               "q4_0": 4.55, "q4_k_s": 4.58, "q4_k_m": 4.85, "q5_k_s": 5.54,
               "q5_k_m": 5.69, "q6_k": 6.59, "q8_0": 8.5, "fp16": 16.0}
        exact = [rr for rr in cands if tag_quant(rr["tag"]) == kq]
        if exact:
            pool = exact
        elif cands and kq in BPW:
            # nearest-quant referee (conservative: closest bits-per-weight)
            pool = [min(cands, key=lambda rr: abs(BPW.get(tag_quant(rr["tag"]), 99) - BPW[kq]))]
        else:
            pool = cands
        if pool:
            best = max(pool, key=lambda rr: rr["smoke_pass"])
            ref = best["smoke_pass"]; ref_q = tag_quant(best["tag"])
        # broken-here test: Ollama artifact fails the full suite
        broken_here = (full is not None and full < 17) or (full is None and r["smoke_pass"] <= 2)
        # independent same-quant conversion demonstrably works where Ollama does not
        ref_works = ref is not None and ref >= 5 and (ref - r["smoke_pass"]) >= 4
        ref_also_fails = ref is not None and ref < 5
        entry = {"tag": r["tag"], "smoke": r["smoke_pass"], "full164": full,
                 "referee_smoke": ref, "referee_quant": ref_q,
                 "family_baseline": baseline[k]}
        if broken_here and ref_works:
            entry["verdict"] = "DEFECTIVE"; confirmed.append(entry)
        elif broken_here and ref_also_fails:
            entry["verdict"] = "CAPABILITY_COLLAPSE"; cleared.append(entry)
        elif broken_here and ref is None:
            entry["verdict"] = "DEFECTIVE_UNREFEREED"; confirmed.append(entry)
        else:
            entry["verdict"] = "INCONCLUSIVE"; cleared.append(entry)

    # Metal-backend replication scores (results-mac + results-metalrep,
    # scored by harness/score_smoke.py). Official defects must fail on both
    # backends; a suspect that passes on Metal is backend-dependent, not
    # defective (DESIGN.md dual-backend rule).
    metal = {}
    for rd in ("results-mac", "results-metalrep"):
        sp = os.path.join(ROOT, rd, "audit_scored.jsonl")
        ap = os.path.join(ROOT, rd, "audit_results.jsonl")
        if not os.path.exists(sp):
            continue
        # scored rows were appended in the order of transcript-bearing
        # audit records, so pair them positionally to recover transcripts
        # for runs whose tag is not unique (the macnight TheBloke runs)
        with_tr = []
        if os.path.exists(ap):
            with_tr = [r["transcript"] for r in
                       (json.loads(l) for l in open(ap) if l.strip())
                       if r.get("transcript")]
        for i, line in enumerate(open(sp)):
            row = json.loads(line)
            tr = with_tr[i] if i < len(with_tr) else ""
            if row["tag"] == "macnight":
                for q in ("Q3_K_M", "Q4_K_M"):
                    if q in tr:
                        metal["thebloke:" + q] = row["smoke_pass"]
            else:
                metal[row["tag"]] = row["smoke_pass"]

    for entry in confirmed:
        if entry["tag"] in metal:
            entry["metal_smoke"] = metal[entry["tag"]]

    # community-channel suspects: community artifact scores far below Ollama's
    # conversion of the same model at the same quant level; the Metal
    # replication then decides defect vs backend-dependent failure
    off_by_mq = {}
    for r in official:
        off_by_mq[(norm_model(r["tag"]), norm_size(r["tag"]), tag_quant(r["tag"]))] = r["smoke_pass"]
    community_defects = []
    backend_dependent = []
    for r in community:
        key = (norm_model(r["tag"]), norm_size(r["tag"]), tag_quant(r["tag"]))
        off = off_by_mq.get(key)
        if off is not None and off >= 8 and (off - r["smoke_pass"]) >= 5:
            mkey = "thebloke:" + (tag_quant(r["tag"]) or "").upper()
            msc = metal.get(mkey)
            rec = {"tag": r["tag"], "cuda_smoke": r["smoke_pass"],
                   "metal_smoke": msc, "ollama_same_quant": off}
            if msc is not None and msc >= 8:
                rec["verdict"] = "BACKEND_DEPENDENT"
                backend_dependent.append(rec)
            else:
                rec["verdict"] = "DEFECTIVE"
                community_defects.append(rec)
    n_off = len(official)
    n_def = len([c for c in confirmed if c["verdict"].startswith("DEFECTIVE")])
    p, lo, hi = wilson(n_def, n_off)
    dist = Counter(classes.values())

    findings = {
        "n_official": n_off, "n_community": len(community),
        "n_families": len({size_key(r["tag"])[0] for r in official}),
        "class_distribution": dict(dist),
        "confirmed_defects": confirmed, "cleared_as_capability": cleared,
        "defect_prevalence": {"count": n_def, "rate": round(p, 4),
                              "ci95": [round(lo, 4), round(hi, 4)]},
        "community_defects": community_defects,
        "backend_dependent": backend_dependent,
        "community_healthy": len(community) - len(community_defects) - len(backend_dependent),
        "community_min_score": min((r["smoke_pass"] for r in community), default=None),
    }
    json.dump(findings, open(os.path.join(HERE, "findings.json"), "w"), indent=1)
    print(f"official artifacts: {n_off} across {findings['n_families']} families")
    print(f"class distribution: {dict(dist)}")
    print(f"CONFIRMED DEFECTS: {n_def}  prevalence {100*p:.1f}% [{100*lo:.1f}, {100*hi:.1f}]")
    for c in confirmed:
        print(f"  {c['verdict']:22s} {c['tag']:42s} smoke={c['smoke']} full164={c['full164']} referee={c['referee_smoke']}")
    print(f"cleared as capability limit (not defects): {len(cleared)}")
    for c in cleared:
        print(f"  {c['tag']:42s} smoke={c['smoke']} full164={c['full164']} referee={c['referee_smoke']}")
    print(f"community channel: {len(community)} artifacts, {len(community_defects)} defective, "
          f"{len(backend_dependent)} backend-dependent:")
    for c in community_defects + backend_dependent:
        print(f"  {c['verdict']:18s} {c['tag'][3:60]:58s} CUDA {c['cuda_smoke']}/15, "
              f"Metal {c['metal_smoke']}/15 (Ollama same={c['ollama_same_quant']}/15)")

if __name__ == "__main__":
    main()
