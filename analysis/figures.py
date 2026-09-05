#!/usr/bin/env python3
"""Figures for the audit paper. Reads results/audit_scored.jsonl.
Fig 1: smoke-score heatmap, family x quant (official channel) -- the census
       at a glance: healthy majority, the Qwen-3B/phi defect zeros, the
       small-model 2-bit collapse band.
"""
import json, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
FIGS = os.path.join(HERE, "..", "paper", "figs")
os.makedirs(FIGS, exist_ok=True)

QORDER = ["q2_K","q3_K_S","q3_K_M","q3_K_L","q4_0","q4_K_S","q4_K_M",
          "q5_K_S","q5_K_M","q6_K","q8_0","fp16"]

def tag_quant(tag):
    t = tag.lower().replace("-", "_")
    for q in sorted(QORDER, key=len, reverse=True):
        if q.lower() in t:
            return q   # return canonical QORDER form
    return None

def model_size(tag):
    m = re.match(r"([^:]+):([\d.]+[bm])", tag)
    return f"{m.group(1)}:{m.group(2)}" if m else tag.split(":")[0]

def size_value(ms):
    m = re.search(r"([\d.]+)([bm])", ms)
    if not m:
        return 0.0
    return float(m.group(1)) * (1.0 if m.group(2) == "b" else 0.001)

plt.rcParams.update({"font.size": 7, "figure.dpi": 200, "savefig.bbox": "tight"})

rows = [json.loads(l) for l in open(os.path.join(RES, "audit_scored.jsonl"))]
official = [r for r in rows if r.get("channel") == "ollama-official"]

# build matrix: rows = model:size (sorted by family then size), cols = quant
cells = {}
for r in official:
    ms = model_size(r["tag"]); q = tag_quant(r["tag"])
    if q:
        cells[(ms, q)] = r["smoke_pass"]
models = sorted({ms for (ms, q) in cells}, key=lambda x: (x.split(":")[0], size_value(x)))
import numpy as np
M = np.full((len(models), len(QORDER)), np.nan)
for i, ms in enumerate(models):
    for j, q in enumerate(QORDER):
        if (ms, q) in cells:
            M[i, j] = cells[(ms, q)]

fig, ax = plt.subplots(figsize=(5.2, 8.0))
cmap = plt.cm.RdYlGn.copy(); cmap.set_bad("#e8e8e8")
im = ax.imshow(M, aspect="auto", cmap=cmap, vmin=0, vmax=15)
ax.set_xticks(range(len(QORDER))); ax.set_xticklabels(QORDER, rotation=45, ha="right", fontsize=6)
ax.set_yticks(range(len(models))); ax.set_yticklabels(models, fontsize=5.5)
for i in range(len(models)):
    for j in range(len(QORDER)):
        if not np.isnan(M[i, j]):
            v = int(M[i, j])
            ax.text(j, i, v, ha="center", va="center", fontsize=4.5,
                    color="white" if v < 4 or v > 12 else "black")
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
cb.set_label("smoke-suite pass (/15)", fontsize=6)
ax.set_title("Functional smoke score, official library (family $\\times$ quantization)", fontsize=7)
fig.savefig(os.path.join(FIGS, "fig1_heatmap.pdf"))
fig.savefig(os.path.join(FIGS, "fig1_heatmap.png"))
print("wrote fig1_heatmap ({} models x {} quants)".format(len(models), len(QORDER)))
