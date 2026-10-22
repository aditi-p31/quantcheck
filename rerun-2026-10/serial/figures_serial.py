#!/usr/bin/env python3
"""Figures for the revised paper, from SERIAL scores (copy of ../figures_v3.py).

Changes against figures_v3.py: the census heatmap reads the serial per-task results
(census_smoke_serial.jsonl) and the numbers come from numbers_serial.json (serial rerun scores);
layout for >= 8 pt text at final size: FS = MIN_PT = 8.0, TEXTWIDTH = 516 pt (IEEEtran \\textwidth),
census heatmap LEFT, RIGHT = 0.47, 0.03, LAB_H = 1.10, key text "15-task suite: tasks passed" with the
suspect key shifted right; calibration figure with a two-column legend and L2, R2, B2, T2 = 0.46, 0.02,
0.32, 0.66. Output goes to ./figs/.

Fig. 1 (figure*, \\textwidth = 516 pt = 7.14 in): census smoke-score heatmap with the serial per-task results
        (census_smoke_serial.jsonl, summed over the 15 suite tasks). One column per model variant, keyed by the
        full registry tag minus its quantization suffix, so every one of the 305 official artifacts appears
        exactly once; one row per quantization level. Single-hue sequential scale; grey = tag not offered
        at or under 8 GB; red boxes = the seven suspects.
Fig. 2 (figure*, 0.92 \\textwidth): full 164-task pass counts at the failing levels: registry tag (= our
        plain rebuild with the registry's tensor mix) vs calibrated builds of the same weights at the same
        level, with the 4-bit registry tag as reference. For phi3.5 Q2_K the group also shows our plain
        rebuild with llama.cpp's current tensor mix (21), the like-for-like comparator of our WikiText
        imatrix build (37); the bartowski build keeps the registry's mix.

Both figures are drawn at their final printed width, so the font size set here is the printed size.
A layout check after each render asserts that every text is at least MIN_PT at final size, lies inside
the figure, and overlaps no other text.
"""
import json, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.text import Text
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))              # paper-v3/analysis/serial
P2 = os.environ.get("QUANTCHECK_ROOT", os.path.abspath(os.path.join(HERE, "..", "..")))
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)
N = json.load(open(os.path.join(HERE, "numbers_serial.json")))
SUITE = json.load(open(os.path.join(P2, "smoke_suite_v1.json")))["suite_tasks"]
assert len(SUITE) == 15

TEXTWIDTH = 516 / 72.27  # IEEEtran conference \textwidth (516 pt), inches
MIN_PT = 8.0
FS = 8.0          # base font size = printed size (figures are drawn at final width)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#dddcd7"
GREY, BLUE, ORANGE, AQUA, YELLOW = "#8a8984", "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
NOT_OFFERED, SUSPECT_RED = "#efefec", "#e34948"
plt.rcParams.update({
    "font.size": FS, "font.family": "serif", "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42,  # TrueType embedding, no Type 3
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS, "axes.labelsize": FS,
    "savefig.dpi": 300, "hatch.linewidth": 0.7,
})


def check_layout(fig, name, target_w, extra_boxes=()):
    """Assert printed font sizes, containment and absence of text collisions; return a summary dict."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    scale = target_w / fig.get_figwidth()
    fb = fig.bbox
    texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    boxes = []
    for t in texts:
        bb = t.get_window_extent(r)
        assert t.get_fontsize() * scale >= MIN_PT - 1e-9, (name, t.get_text(), t.get_fontsize() * scale)
        assert bb.x0 >= fb.x0 - 0.5 and bb.x1 <= fb.x1 + 0.5 and bb.y0 >= fb.y0 - 0.5 and bb.y1 <= fb.y1 + 0.5, \
            (name, "outside figure", t.get_text())
        boxes.append((t.get_text(), bb))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.x0 < b.x1 - 0.3 and b.x0 < a.x1 - 0.3 and a.y0 < b.y1 - 0.3 and b.y0 < a.y1 - 0.3:
                raise AssertionError(f"{name}: text collision {boxes[i][0]!r} / {boxes[j][0]!r}")
    for label, bb2 in extra_boxes:
        for txt, bb in boxes:
            if bb.x0 < bb2.x1 and bb2.x0 < bb.x1 and bb.y0 < bb2.y1 and bb2.y0 < bb.y1:
                raise AssertionError(f"{name}: text {txt!r} collides with {label}")
    return {"fig_in": (round(fig.get_figwidth(), 3), round(fig.get_figheight(), 3)),
            "printed_in": (round(target_w, 3), round(fig.get_figheight() * scale, 3)),
            "min_pt": round(min(t.get_fontsize() for t in texts) * scale, 2), "n_texts": len(texts)}


# ---------- Fig. 1 ----------
QORDER = ["q2_K", "q3_K_S", "q3_K_M", "q3_K_L", "q4_0", "q4_K_S", "q4_K_M", "q5_0", "q5_K_S", "q5_K_M",
          "q6_K", "q8_0", "fp16"]
DROP_TOKENS = {"instruct", "chat", "it", "mini", "lite"}  # role words and size descriptors; versions/context kept


def split_tag(tag, quant):
    """Full tag minus its quantization suffix -> (variant key, display label)."""
    assert tag.endswith("-" + quant), tag
    key = tag[: -len(quant) - 1]
    family, rest = key.split(":", 1)
    label = " ".join([family] + [t for t in rest.split("-") if t not in DROP_TOKENS])
    return key, label


def size_value(key):
    m = re.match(r"[^:]+:([\d.]+)([bm])", key)
    return float(m.group(1)) * (1.0 if m.group(2) == "b" else 0.001)


rescore = {}
for l in open(os.path.join(HERE, "census_smoke_serial.jsonl")):
    r = json.loads(l)
    assert set(r["per_task"]) == set(SUITE), r["tag"]
    rescore[r["tag"]] = sum(1 for t in SUITE if r["per_task"][t])
official = [r for r in map(json.loads, open(os.path.join(P2, "results", "audit_scored.jsonl")))
            if r["channel"] == "ollama-official"]
cells, labels = {}, {}
for r in official:
    key, label = split_tag(r["tag"], r["quant"])
    assert (key, r["quant"]) not in cells, ("duplicate cell", r["tag"])
    cells[(key, r["quant"])] = rescore[r["tag"]]
    assert labels.setdefault(key, label) == label
assert len(official) == N["census"]["official"] == 305
assert len(cells) == 305, len(cells)                       # every official artifact appears exactly once
assert len(set(labels.values())) == len(labels)            # display labels are unique
assert sum(1 for v in cells.values() if v < 9) == N["stage1_flags_rescored"] == 39   # serial: 39 (pool rescore: 43)
used_q = [q for q in QORDER if any(k[1] == q for k in cells)]
variants = sorted(labels, key=lambda k: (k.split(":")[0], size_value(k), k))
assert len({k.split(":")[0] for k in variants}) == N["census"]["lines"]
M = np.full((len(used_q), len(variants)), np.nan)          # rows = levels, columns = variants
for (key, q), v in cells.items():
    M[used_q.index(q), variants.index(key)] = v
assert int(np.sum(~np.isnan(M))) == 305
suspects = set()
for s in N["suspects"]:
    q = next(q for q in sorted(QORDER, key=len, reverse=True) if s["tag"].endswith("-" + q))
    suspects.add(split_tag(s["tag"], q)[0] + "|" + q)
    assert cells[(split_tag(s["tag"], q)[0], q)] == s["smoke_rescored"], s
assert len(suspects) == 7

nR, nC = M.shape
W1 = TEXTWIDTH
LEFT, RIGHT = 0.47, 0.03            # row-label gutter, right margin (in)
KEY_H, GAP = 0.24, 0.10             # key strip above the heatmap, gap between key and heatmap
ROW_H = 0.15
HM_W, HM_H = W1 - LEFT - RIGHT, nR * ROW_H
LAB_H = 1.10                        # rotated column labels under the heatmap
BOT = LAB_H + 0.02
H1 = BOT + HM_H + GAP + KEY_H
fig = plt.figure(figsize=(W1, H1))
ax = fig.add_axes([LEFT / W1, BOT / H1, HM_W / W1, HM_H / H1])
cmap = plt.cm.Blues.copy()
cmap.set_bad(NOT_OFFERED)
im = ax.imshow(np.ma.masked_invalid(M), aspect="auto", cmap=cmap, vmin=0, vmax=15, interpolation="nearest")
fam = [k.split(":")[0] for k in variants]
for j in range(nC - 1):            # thin cell rules; wider gap between model lines
    ax.axvline(j + 0.5, color="white", lw=2.0 if fam[j] != fam[j + 1] else 0.5, zorder=2)
for i in range(nR - 1):
    ax.axhline(i + 0.5, color="white", lw=0.5, zorder=2)
for i, q in enumerate(used_q):
    for j, key in enumerate(variants):
        if np.isnan(M[i, j]):
            continue
        v = int(M[i, j])
        ax.text(j, i, str(v), ha="center", va="center", fontsize=FS, color="white" if v >= 11 else INK, zorder=3)
        if f"{key}|{q}" in suspects:
            ax.add_patch(Rectangle((j - 0.44, i - 0.42), 0.88, 0.84, fill=False, edgecolor=SUSPECT_RED,
                                   lw=1.3, zorder=4))
ax.set_xticks(range(nC))
ax.set_xticklabels([labels[k] for k in variants], rotation=90, ha="center", va="top", color=INK)
ax.set_yticks(range(nR))
ax.set_yticklabels(used_q, color=INK)
ax.tick_params(length=0, pad=2.5)
for s in ax.spines.values():
    s.set_visible(False)

# key strip: colour scale, not-offered swatch, suspect box (inch coordinates)
key = fig.add_axes([0, (BOT + HM_H + GAP) / H1, 1, KEY_H / H1])
key.set_xlim(0, W1)
key.set_ylim(0, KEY_H)
key.axis("off")
yc = KEY_H * 0.62
key.text(LEFT, yc, "15-task suite: tasks passed", ha="left", va="center", fontsize=FS, color=INK)
cb_x0, cb_w, cb_h = LEFT + 1.62, 1.6, 0.085
key.imshow(np.linspace(0, 15, 256)[None, :], cmap=cmap, vmin=0, vmax=15, aspect="auto",
           extent=(cb_x0, cb_x0 + cb_w, yc - cb_h / 2, yc + cb_h / 2))
for v in (0, 5, 10, 15):
    xv = cb_x0 + cb_w * v / 15
    key.plot([xv, xv], [yc - cb_h / 2 - 0.02, yc - cb_h / 2], color=MUTED, lw=0.5)
    key.text(xv, yc - cb_h / 2 - 0.025, str(v), ha="center", va="top", fontsize=FS, color=MUTED)
sw = 0.13
x_no = cb_x0 + cb_w + 0.45
key.add_patch(Rectangle((x_no, yc - 0.05), sw, 0.10, facecolor=NOT_OFFERED, edgecolor=GREY, lw=0.4))
key.text(x_no + sw + 0.06, yc, "Tag not offered at or under 8 GB", ha="left", va="center", fontsize=FS, color=INK)
x_su = x_no + sw + 0.06 + 1.85
key.add_patch(Rectangle((x_su, yc - 0.05), sw, 0.10, facecolor="white", edgecolor=SUSPECT_RED, lw=1.3))
key.text(x_su + sw + 0.06, yc, "Suspect", ha="left", va="center", fontsize=FS, color=INK)

info1 = check_layout(fig, "fig1", TEXTWIDTH)
fig.savefig(os.path.join(FIGS, "fig1_census.pdf"))
fig.savefig(os.path.join(FIGS, "fig1_census.png"))
plt.close(fig)
print(f"fig1: {nR} level rows x {nC} variant columns ({len(set(fam))} lines), "
      f"{int(np.sum(~np.isnan(M)))} artifacts, {len(suspects)} suspects boxed; {info1}")

# ---------- Fig. 2 ----------
R6, P0c = N["R6"], N["P0c"]
groups = ["Qwen 3B\nQ2_K", "Qwen 3B\nQ3_K_S", "Qwen 3B\nQ3_K_M", "Qwen 3B\nQ3_K_L", "phi3.5 3.8B\nQ2_K"]
LBL_REG = "Registry tag (= our plain rebuild, registry tensor mix)"
LBL_PLAIN = "Our plain rebuild, current tensor mix (phi3.5)"
LBL_WIKI = "Our rebuild + importance matrix (WikiText)"
LBL_CODE = "Our rebuild + importance matrix (code)"
LBL_BART = "Third-party importance matrix (bartowski)"
LBL_AWQ = "Model author's AWQ build"
LBL_REF = "Registry 4-bit tag (q4_K_M), same model"
STYLE = {LBL_REG: dict(color=GREY), LBL_PLAIN: dict(color="white", edgecolor=GREY, hatch="//////"),
         LBL_WIKI: dict(color=BLUE), LBL_CODE: dict(color=ORANGE), LBL_BART: dict(color=AQUA),
         LBL_AWQ: dict(color=YELLOW)}
# Qwen groups keep the series order; the phi3.5 group is ordered by tensor mix (registry mix: tag and
# bartowski; current mix: our plain and WikiText-imatrix rebuilds) so each like-for-like pair is adjacent.
data = [
    [(LBL_REG, 0), (LBL_WIKI, R6["cal-qwen3b-Q2_K"]), (LBL_CODE, P0c["codeimat-qwen3b-Q2_K"]),
     (LBL_BART, R6["imat-qwen3b-Q2_K"]), (LBL_AWQ, R6["awq-qwen3b-q2_k"])],
    [(LBL_REG, 0), (LBL_WIKI, R6["cal-qwen3b-Q3_K_S"]), (LBL_CODE, P0c["codeimat-qwen3b-Q3_K_S"]),
     (LBL_BART, P0c["imat-qwen3b-Q3_K_S"]), (LBL_AWQ, None)],
    [(LBL_REG, 0), (LBL_WIKI, R6["cal-qwen3b-Q3_K_M"]), (LBL_CODE, P0c["codeimat-qwen3b-Q3_K_M"]),
     (LBL_BART, P0c["imat-qwen3b-Q3_K_M"]), (LBL_AWQ, R6["awq-qwen3b-q3_k_m"])],
    [(LBL_REG, 0), (LBL_WIKI, R6["cal-qwen3b-Q3_K_L"]), (LBL_CODE, P0c["codeimat-qwen3b-Q3_K_L"]),
     (LBL_BART, P0c["imat-qwen3b-Q3_K_L"]), (LBL_AWQ, None)],
    [(LBL_REG, P0c["libmix-phi35-Q2_K"]), (LBL_BART, P0c["imat-phi35-Q2_K"]),
     (LBL_PLAIN, P0c["plain-phi35-Q2_K"]), (LBL_WIKI, P0c["cal-phi35-Q2_K"])],
]
assert P0c["libmix-phi35-Q2_K"] == 0 and P0c["plain-phi35-Q2_K"] == 21 and P0c["cal-phi35-Q2_K"] == 37
ref = [R6["lib-qwen3b-q4_K_M"]] * 4 + [P0c["lib-phi35-q4_K_M"]]
w = 0.16
offsets = [[(k - 2) * w for k in range(5)]] * 4 + [[-2.1 * w, -1.1 * w, 1.1 * w, 2.1 * w]]

W2 = 0.92 * TEXTWIDTH
L2, R2, B2, T2 = 0.46, 0.02, 0.32, 0.66
AX_H = 1.55
H2 = B2 + AX_H + T2
fig = plt.figure(figsize=(W2, H2))
ax = fig.add_axes([L2 / W2, B2 / H2, (W2 - L2 - R2) / W2, AX_H / H2])
x = np.arange(len(groups))
ax.set_xlim(-0.55, len(groups) - 0.45)
ax.set_ylim(0, 164)
inside = []
for g, items in enumerate(data):
    for (label, v), off in zip(items, offsets[g]):
        if v is None:
            continue
        xpos = x[g] + off
        if v == 0:
            ax.plot([xpos - w * 0.38, xpos + w * 0.38], [0.8, 0.8], color=GREY, lw=2.2, solid_capstyle="round")
            ax.text(xpos, 4, "0", ha="center", va="bottom", fontsize=FS, color=INK)
            continue
        st = dict(STYLE[label])
        ax.bar(xpos, v, w * 0.86, color=st.pop("color"), edgecolor=st.pop("edgecolor", "white"),
               linewidth=0.7 if label == LBL_PLAIN else 0.6, **st)
        if v + 2 + 13 > ref[g] - 1 and v < ref[g] + 2:      # label would cross the dashed reference
            ax.text(xpos, v - 2.5, str(v), ha="center", va="top", fontsize=FS, color=INK)
            inside.append(v)
        else:
            ax.text(xpos, v + 2, str(v), ha="center", va="bottom", fontsize=FS, color=MUTED)
ref_lines = []
for g in range(len(groups)):
    ref_lines += ax.plot([x[g] - 0.45, x[g] + 0.45], [ref[g], ref[g]], color=MUTED, lw=0.8,
                         ls=(0, (3, 2)), zorder=0)
# brackets marking the two same-mix pairs in the phi3.5 group
g = 4
brackets = []
for (a, b), txt in (((0, 1), "registry mix"), ((2, 3), "current mix")):
    xa, xb = x[g] + offsets[g][a] - w * 0.43, x[g] + offsets[g][b] + w * 0.43
    yb = 56     # figures_v3: 52; at 8 pt the "37" label reached the bracket's end tick
    brackets += ax.plot([xa, xa, xb, xb], [yb - 3, yb, yb, yb - 3], color=MUTED, lw=0.6)
    ax.text((xa + xb) / 2, yb + 2, txt, ha="center", va="bottom", fontsize=FS, color=MUTED, linespacing=1.0)
handles = [Patch(facecolor=GREY, edgecolor="white", label=LBL_REG),
           Patch(facecolor="white", edgecolor=GREY, hatch="//////", lw=0.7, label=LBL_PLAIN),
           Patch(facecolor=BLUE, label=LBL_WIKI), Patch(facecolor=ORANGE, label=LBL_CODE),
           Patch(facecolor=AQUA, label=LBL_BART), Patch(facecolor=YELLOW, label=LBL_AWQ),
           Line2D([0], [0], color=MUTED, lw=0.8, ls=(0, (3, 2)), label=LBL_REF)]
ax.set_xticks(x)
ax.set_xticklabels(groups, color=INK)
ax.set_ylabel("HumanEval+ tasks passed (of 164)")
ax.set_yticks([0, 40, 80, 120, 160])
ax.grid(axis="y", color=GRID, lw=0.5)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
fig.legend(handles=handles, ncol=2, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.0),
           handlelength=1.6, handleheight=0.9, columnspacing=1.0, handletextpad=0.5, labelspacing=0.3,
           borderaxespad=0.1, borderpad=0.1)
fig.canvas.draw()
rend = fig.canvas.get_renderer()
info2 = check_layout(fig, "fig2", 0.92 * TEXTWIDTH,
                     extra_boxes=[("dashed reference line", ln.get_window_extent(rend).expanded(1.0, 1.0).padded(1.5))
                                  for ln in ref_lines]
                                 + [("phi3.5 bracket", ln.get_window_extent(rend).padded(1.5)) for ln in brackets])
fig.savefig(os.path.join(FIGS, "fig2_calibration.pdf"))
fig.savefig(os.path.join(FIGS, "fig2_calibration.png"))
plt.close(fig)
print(f"fig2: {len(groups)} groups; labels inside bars for {inside}; {info2}")
