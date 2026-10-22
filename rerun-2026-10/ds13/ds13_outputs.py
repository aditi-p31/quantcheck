import os
#!/usr/bin/env python3
"""F05 diagnosis, step 2: what deepseek-coder-1.3b census outputs look like,
compared with deepseek-coder-6.7b (same Ollama template, system prompt and
mis-pre-tokenized prompts), the TheBloke 1.3b referee, and two healthy small
coders. Static analysis only: generated code is parsed, never executed.
Writes gates/ds13/outputs_summary.json.
"""
import ast, glob, json, os, re, statistics, sys, warnings
warnings.filterwarnings("ignore")
from evalplus.data import get_human_eval_plus
from evalplus.sanitize import sanitize

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
DS = os.path.join(V3, "gates", "ds13")
RESCORE = os.environ.get("QUANTCHECK_RESCORE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "census_rescore.jsonl"))
FENCE = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)(?:```|\Z)", re.S)
REFUSAL = re.compile(r"I'm sorry|I am sorry|I cannot|I can't|As an AI|only answer questions related to computer science", re.I)

def first_block(sol):
    m = FENCE.search(sol)
    return (m.group(1).lower(), m.group(2)) if m else (None, sol)

def analyse(path, per_task=None):
    tasks = get_human_eval_plus()
    rows = [json.loads(l) for l in open(path) if l.strip()]
    out = {"n": len(rows), "fence": 0, "lang_other": 0, "closed_fence": 0, "parse_ok": 0,
           "indent_err": 0, "syntax_err": 0, "entry_def_raw": 0, "entry_in_sanitized": 0,
           "odd_indent_outputs": 0, "refusal": 0, "chars": [], "comment_share": [],
           "pass": None, "fail_parse_err": 0, "fail_n": 0}
    for r in rows:
        tid, sol = r["task_id"], r["solution"]
        ep = tasks[tid]["entry_point"]
        lang, code = first_block(sol)
        if lang is not None:
            out["fence"] += 1
            if lang not in ("python", "py", "python3", ""):
                out["lang_other"] += 1
            if sol.count("```") >= 2:
                out["closed_fence"] += 1
        perr = None
        try:
            ast.parse(code)
            out["parse_ok"] += 1
        except IndentationError:
            out["indent_err"] += 1; perr = "indent"
        except SyntaxError:
            out["syntax_err"] += 1; perr = "syntax"
        if re.search(r"(?m)^\s*def\s+%s\s*\(" % re.escape(ep), code):
            out["entry_def_raw"] += 1
        try:
            s = sanitize(sol, ep)
        except Exception:
            s = ""
        if re.search(r"(?m)^def\s+%s\s*\(" % re.escape(ep), s):
            out["entry_in_sanitized"] += 1
        lines = [l for l in code.splitlines() if l.strip()]
        ind = [len(l) - len(l.lstrip(" ")) for l in lines]
        if any(i % 4 == 1 and i >= 5 for i in ind):
            out["odd_indent_outputs"] += 1
        if REFUSAL.search(sol):
            out["refusal"] += 1
        out["chars"].append(len(sol))
        com = sum(len(m) for m in re.findall(r"#[^\n]*", code))
        out["comment_share"].append(com / max(1, len(code)))
        if per_task is not None and tid in per_task and not per_task[tid]:
            out["fail_n"] += 1
            if perr:
                out["fail_parse_err"] += 1
    if per_task is not None:
        out["pass"] = sum(1 for r in rows if per_task.get(r["task_id"]))
    out["median_chars"] = int(statistics.median(out.pop("chars")))
    out["mean_comment_share"] = round(statistics.mean(out.pop("comment_share")), 3)
    return out

def main():
    resc = {}
    for l in open(RESCORE):
        r = json.loads(l); resc[r["transcript"]] = r["per_task"]
    groups = {
        "ds1.3b_ollama_smoke": sorted(glob.glob(os.path.join(DS, "results/transcripts/deepseek-coder_1.3b-*.jsonl"))),
        "ds1.3b_thebloke_smoke": glob.glob(os.path.join(DS, "results/transcripts/hf_TheBloke_deepseek-coder-1.3b*.jsonl")),
        "ds6.7b_ollama_smoke": sorted(glob.glob(os.path.join(DS, "compare/results/transcripts/deepseek-coder_6.7b-*.jsonl"))),
        "ds6.7b_thebloke_smoke(empty template)": glob.glob(os.path.join(DS, "compare/results/transcripts/hf_TheBloke_deepseek-coder-6.7B*.jsonl")),
        "yi-coder1.5b_smoke": sorted(glob.glob(os.path.join(DS, "compare/results/transcripts/yi-coder_1.5b-*.jsonl"))),
        "qwen2.5-coder1.5b_smoke": sorted(glob.glob(os.path.join(DS, "compare/results/transcripts/qwen2.5-coder_1.5b-*.jsonl"))),
    }
    result = {}
    for g, files in groups.items():
        smoke = [f for f in files if not f.endswith(".full164.jsonl")]
        full = [f for f in files if f.endswith(".full164.jsonl")]
        for kind, fl in (("smoke", smoke), ("full164", full)):
            for f in fl:
                base = os.path.basename(f)
                key = base.replace(".smoke.jsonl", ".jsonl")
                pt = (resc.get(base) or resc.get(key)) if kind == "smoke" else None
                a = analyse(f, pt)
                result.setdefault(g, {})[base] = a
    json.dump(result, open(os.path.join(DS, "outputs_summary.json"), "w"), indent=1)
    # compact print
    agg_keys = ["n", "pass", "fence", "lang_other", "closed_fence", "parse_ok", "indent_err", "syntax_err",
                "entry_def_raw", "entry_in_sanitized", "odd_indent_outputs", "refusal", "fail_n", "fail_parse_err"]
    for g, d in result.items():
        for kind in ("smoke", "full164"):
            items = {k: v for k, v in d.items() if k.endswith(".full164.jsonl") == (kind == "full164")}
            if not items:
                continue
            tot = {k: sum((v.get(k) or 0) for v in items.values()) for k in agg_keys}
            med = statistics.median(v["median_chars"] for v in items.values())
            com = statistics.mean(v["mean_comment_share"] for v in items.values())
            print(f"{g:40s} {kind:8s} files={len(items):2d} " + " ".join(f"{k}={tot[k]}" for k in agg_keys)
                  + f" median_chars={med} comment_share={com:.3f}")
    for f, v in result["ds1.3b_ollama_smoke"].items():
        if f.endswith(".full164.jsonl"):
            print(f, {k: v[k] for k in ("n", "parse_ok", "indent_err", "syntax_err", "entry_in_sanitized", "odd_indent_outputs", "closed_fence", "refusal")})

if __name__ == "__main__":
    main()
