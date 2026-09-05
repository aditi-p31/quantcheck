#!/usr/bin/env python3
"""Final artifact classification (two-stage, family-relative).

Stage 1 (screen, done on pod): flat 60% smoke threshold -> "flagged".
Stage 2 (this script): family-size baseline = median smoke_pass over the
same family+size high-precision builds (q6_K, q8_0, fp16; fallback: max
of available quants). Classes:

  DEFECTIVE  ratio < 0.20 of baseline (design threshold) AND baseline >= 8
             (family demonstrably capable on the suite)
  COLLAPSED  ratio < 0.20 but baseline < 8 (family too weak for the suite
             to certify; needs full-run + cross-distributor evidence)
  DEGRADED   0.20 <= ratio < 0.60
  HEALTHY    ratio >= 0.60
  NO_BASELINE high-precision builds unavailable (classify via cross-
             distributor or full run)

Borderline queue: every DEFECTIVE/COLLAPSED artifact plus DEGRADED ones
within 1 task of a boundary -> full 164-task evaluation + manual
transcript inspection before the paper labels anything.

Usage: python3 classify.py <audit_scored.jsonl> [more files...]
"""
import json, re, statistics, sys
from collections import defaultdict

HIGH = {"q6_K", "q8_0", "fp16", "f16"}

def size_key(tag):
    # qwen2.5-coder:3b-instruct-q3_K_M -> ("qwen2.5-coder", "3b")
    m = re.match(r"([^:]+):([\d.]+b)", tag)
    return (m.group(1), m.group(2)) if m else (tag.split(":")[0], "?")

def main(paths):
    rows = []
    seen = set()
    for p in paths:
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["tag"] in seen:      # later files (mac confirmations) don't dup
                continue
            seen.add(r["tag"])
            rows.append(r)
    fam = defaultdict(list)
    for r in rows:
        fam[size_key(r["tag"])].append(r)

    out = []
    for key, group in sorted(fam.items()):
        base_scores = [g["smoke_pass"] for g in group if g.get("quant") in HIGH
                       or any(h in g["tag"] for h in ("q6_K", "q8_0", "fp16"))]
        baseline = statistics.median(base_scores) if base_scores else None
        for g in sorted(group, key=lambda x: x["tag"]):
            s = g["smoke_pass"]
            if baseline is None:
                cls = "NO_BASELINE"
                ratio = None
            else:
                ratio = s / baseline if baseline else 0.0
                if ratio < 0.20:
                    cls = "DEFECTIVE" if baseline >= 8 else "COLLAPSED"
                elif ratio < 0.60:
                    cls = "DEGRADED"
                else:
                    cls = "HEALTHY"
            needs_full = cls in ("DEFECTIVE", "COLLAPSED", "NO_BASELINE") or (
                cls == "DEGRADED" and baseline and abs(s - 0.2 * baseline) <= 1)
            out.append({"tag": g["tag"], "family_size": "/".join(key),
                        "smoke_pass": s, "baseline": baseline,
                        "ratio": round(ratio, 3) if ratio is not None else None,
                        "class": cls, "needs_full_run": needs_full,
                        "channel": g.get("channel")})
    json.dump(out, open("classified.json", "w"), indent=1)
    from collections import Counter
    c = Counter(o["class"] for o in out)
    print(f"{len(out)} artifacts classified: {dict(c)}")
    for o in out:
        if o["class"] != "HEALTHY":
            print(f"  {o['class']:11s} {o['tag']:46s} {o['smoke_pass']:>2}/15 "
                  f"baseline={o['baseline']} ratio={o['ratio']}"
                  + (" [FULL-RUN QUEUE]" if o["needs_full_run"] else ""))

if __name__ == "__main__":
    main(sys.argv[1:] or ["../results/audit_scored.jsonl"])
