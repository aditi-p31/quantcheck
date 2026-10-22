#!/usr/bin/env python3
"""Extra checks on specific A1 claims (stdlib only, read-only on inputs).
Reads the census archive in memory (tarfile, no extraction).
Run: python3 -I -B verify_extra.py  -> verify_extra.json
"""
import sys
sys.dont_write_bytecode = True
import glob, importlib.util, itertools, json, math, os, re, statistics, tarfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.environ.get("QUANTCHECK_ROOT", os.path.abspath(os.path.join(HERE, "..", "..", "..")))
# P1 calibration evaluation files are not part of this repository; point QUANTCHECK_P1_RESULTS at them.
P1R = os.environ.get("QUANTCHECK_P1_RESULTS", os.path.join(P2, "p1_results"))
spec = importlib.util.spec_from_file_location("p2_analyze", os.path.join(P2, "analysis", "analyze.py"))
an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)
out = {}

# --- HE/15 generations in archived census transcripts (text check only)
tf = tarfile.open(os.path.join(P2, "results", "audit_data_full.tgz"))
pat_join = re.compile(r"join\s*\(")
pat_rng = re.compile(r"range\s*\(\s*(0\s*,\s*)?n\s*\+\s*1\s*\)")
cnt = Counter(); nfiles = Counter()
for m in tf.getmembers():
    if not (m.isfile() and m.name.startswith("results/transcripts/") and m.name.endswith(".jsonl")):
        continue
    kind = "full164" if ".full164." in m.name else ("smoke" if ".smoke." in m.name else "plain")
    nfiles[kind] += 1
    if kind == "full164":
        continue
    for line in tf.extractfile(m).read().decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("task_id") == "HumanEval/15":
            sol = r.get("solution") or ""
            cnt["canonical" if (pat_join.search(sol) and pat_rng.search(sol)) else "other"] += 1
out["he15_text_check"] = {"files": dict(nfiles), "he15_generations": dict(cnt)}

# --- census vs P1 for the same Qwen artifacts
def load_p1(bench):
    res = {}
    for f in sorted(glob.glob(os.path.join(P1R, "*.%s.samples-sanitized_eval_results.json" % bench))):
        cfg = os.path.basename(f).split("." + bench)[0]
        res[cfg] = {t: v[0]["base_status"] == "pass" and v[0]["plus_status"] == "pass"
                    for t, v in json.load(open(f))["eval"].items()}
    return res, {cfg: {t: (v[0]["base_status"], v[0]["plus_status"]) for t, v in json.load(open(f))["eval"].items()}
                 for f in sorted(glob.glob(os.path.join(P1R, "*.%s.samples-sanitized_eval_results.json" % bench)))
                 for cfg in [os.path.basename(f).split("." + bench)[0]]}
he, he_raw = load_p1("humaneval")
mb, _ = load_p1("mbpp")
suite = json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"]
rows = [json.loads(l) for l in open(os.path.join(P2, "results", "audit_scored.jsonl")) if l.strip()]
off = {r["tag"]: r for r in rows if r.get("channel") == "ollama-official"}
cmp_rows = {}; dis = Counter()
for cfg in he:
    tag = cfg.replace("_", ":", 1)
    if tag in off:
        p1 = sum(he[cfg][t] for t in suite); cs = off[tag]["smoke_pass"]
        for t in suite:
            if he[cfg][t] != off[tag]["per_task"][t]:
                dis[t] += 1
        cmp_rows[cfg] = [p1, cs]
out["census_vs_p1"] = {"n_in_census": len(cmp_rows), "scores_p1_census": cmp_rows, "task_disagreements": dict(dis)}

# --- pass-definition robustness of the 39-task pool
healthy = [c for c in he if c != "qwen2.5-coder_3b-instruct-q3_K_M"]
tasks = list(he_raw[healthy[0]].keys())
defs = {"base_and_plus": lambda b, p: b == "pass" and p == "pass",
        "plus_only": lambda b, p: p == "pass", "base_only": lambda b, p: b == "pass"}
pool = {}
for name, fn in defs.items():
    a = sorted(t for t in tasks if all(fn(*he_raw[c][t]) for c in healthy))
    pool[name] = {"n": len(a), "first15_lex_equals_suite": sorted(a)[:15] == suite}
out["pool_by_pass_definition"] = pool

# --- census subset checks: phi misses vs HE/15; scaling sensitivity; extra suspects
offl = list(off.values()); tags = [r["tag"] for r in offl]
TI = {t: i for i, t in enumerate(suite)}
mask = {r["tag"]: sum(1 << TI[t] for t, ok in r["per_task"].items() if ok) for r in offl}
key = {t: an.size_key(t) for t in tags}
groups = defaultdict(list)
for t in tags:
    groups[key[t]].append(t)
hi = {k: [t for t in g if any(h in t for h in an.HIGH)] for k, g in groups.items()}
D4 = ["qwen2.5-coder:3b-instruct-q2_K", "qwen2.5-coder:3b-instruct-q3_K_S",
      "qwen2.5-coder:3b-instruct-q3_K_M", "qwen2.5-coder:3b-instruct-q3_K_L"]
PHI = "phi3.5:3.8b-mini-instruct-q2_K"
pc = lambda x: bin(x).count("1")

def suspects(S, k, cap_fn, base_fn):
    sc = {t: pc(mask[t] & S) for t in tags}
    base = {kk: (statistics.median([sc[x] for x in h]) if h else None) for kk, h in hi.items()}
    su = set()
    for t in tags:
        s = sc[t]; b = base[key[t]]
        if b is None:
            continue
        if (s / b if b else 0) >= 0.6:
            continue
        if s <= cap_fn(k) and b >= base_fn(k):
            su.add(t)
    return su

scalings = {
    "exact_rational(A1)": (lambda k: 2 * k / 15, lambda k: 8 * k / 15),
    "cap_ceil": (lambda k: math.ceil(2 * k / 15), lambda k: 8 * k / 15),
    "cap_round_base_floor": (lambda k: round(2 * k / 15), lambda k: math.floor(8 * k / 15)),
}
full = suspects((1 << 15) - 1, 15, *scalings["exact_rational(A1)"])
assert len(full) == 7
sens = {}
phi_miss = {}
extra = {}
for k in (3, 4, 5, 10, 14):
    for name, (cf, bf) in scalings.items():
        js = n = 0; c4 = c5 = 0; ex = 0; nonconf = 0
        miss_with15 = miss = 0
        for comb in itertools.combinations(range(15), k):
            S = sum(1 << i for i in comb)
            su = suspects(S, k, cf, bf)
            n += 1
            js += (len(su & full) / len(su | full)) if (su or full) else 1
            c4 += all(d in su for d in D4); c5 += all(d in su for d in D4 + [PHI])
            ex += len(su - full); nonconf += len(su - set(D4))
            if name.startswith("exact") and PHI not in su:
                miss += 1; miss_with15 += TI["HumanEval/15"] in comb
        sens["k=%d %s" % (k, name)] = {"mean_jaccard_suspects": round(js / n, 4), "all4": round(c4 / n, 4),
                                        "all5": round(c5 / n, 4), "mean_extra_suspects": round(ex / n, 3),
                                        "mean_suspects_not_conf4": round(nonconf / n, 3)}
        if name.startswith("exact"):
            phi_miss[str(k)] = {"misses": miss, "misses_containing_HE15": miss_with15, "n": n}
out["suspect_scaling_sensitivity"] = sens
out["phi_misses_vs_HE15"] = phi_miss

# --- classify.py's older rule on official rows (re-stated; classify.py itself is NOT run,
# because it writes classified.json into the cwd)
def ck_size_key(tag):
    m = re.match(r"([^:]+):([\d.]+b)", tag)
    return (m.group(1), m.group(2)) if m else (tag.split(":")[0], "?")
fam = defaultdict(list)
for r in rows:  # classify.py is invoked on the whole file (all channels)
    fam[ck_size_key(r["tag"])].append(r)
cls = Counter(); defective = []
for kk, g in fam.items():
    bs = [x["smoke_pass"] for x in g if x.get("quant") in {"q6_K", "q8_0", "fp16", "f16"}
          or any(h in x["tag"] for h in ("q6_K", "q8_0", "fp16"))]
    b = statistics.median(bs) if bs else None
    for x in g:
        if x.get("channel") != "ollama-official":
            continue
        s = x["smoke_pass"]
        if b is None:
            c = "NO_BASELINE"
        else:
            ratio = s / b if b else 0.0
            c = ("DEFECTIVE" if b >= 8 else "COLLAPSED") if ratio < 0.2 else ("DEGRADED" if ratio < 0.6 else "HEALTHY")
        cls[c] += 1
        if c == "DEFECTIVE":
            defective.append(x["tag"])
out["classify_py_rule_on_official"] = {"classes": dict(cls), "defective": sorted(defective)}

# --- Spearman HE+ vs MBPP+ over healthy configs
def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for q in range(i, j + 1):
            r[o[q]] = (i + j) / 2 + 1
        i = j + 1
    return r
x = [sum(he[c].values()) for c in healthy]; y = [sum(mb[c].values()) for c in healthy]
rx, ry = ranks(x), ranks(y); mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
rho = sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
out["spearman_he_mbpp_healthy"] = round(rho, 4)
out["mbpp_defect"] = sum(mb["qwen2.5-coder_3b-instruct-q3_K_M"].values())
out["mbpp_healthy_min_rate"] = round(min(y) / 378, 4)

json.dump(out, open(os.path.join(HERE, "verify_extra.json"), "w"), indent=1, sort_keys=True)
print(json.dumps(out, indent=1))
