#!/usr/bin/env python3
"""F05 diagnosis, step 3: share of census smoke outputs whose first code block
does not parse (static ast.parse, nothing executed), for deepseek-coder-1.3B,
the seven suspects, and the other 286 official tags. Reads the census
transcripts in results/transcripts (QUANTCHECK_CENSUS_TRANSCRIPTS overrides; the run
used the copy extracted from results/audit_data_full.tgz, identical for the official tags).
"""
import ast, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.abspath(os.path.join(HERE, "..", ".."))
TD = os.environ.get("QUANTCHECK_CENSUS_TRANSCRIPTS", os.path.join(P2, "results", "transcripts"))
FENCE = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)(?:```|\Z)", re.S)
SUSP = {"qwen2.5-coder:3b-instruct-q2_K", "qwen2.5-coder:3b-instruct-q3_K_S",
        "qwen2.5-coder:3b-instruct-q3_K_M", "qwen2.5-coder:3b-instruct-q3_K_L",
        "phi3.5:3.8b-mini-instruct-q2_K", "llama3.2:1b-instruct-q2_K", "llama3.2:1b-instruct-q3_K_S"}

def main():
    aud = {}
    for l in open(os.path.join(P2, "results", "audit_results.jsonl")):
        r = json.loads(l)
        if r.get("transcript") and r.get("channel") == "ollama-official":
            aud[r["tag"]] = r["transcript"]
    res = {"deepseek-coder-1.3b": [0, 0, 0, 0], "seven_suspects": [0, 0, 0, 0], "other_official": [0, 0, 0, 0]}
    for tag, t in aud.items():
        p = os.path.join(TD, t)
        if not os.path.exists(p):
            p = p.replace(".jsonl", ".smoke.jsonl")
        key = ("deepseek-coder-1.3b" if tag.startswith("deepseek-coder:1.3b")
               else "seven_suspects" if tag in SUSP else "other_official")
        res[key][3] += 1
        for l in open(p):
            s = json.loads(l)["solution"]
            m = FENCE.search(s)
            code = m.group(2) if m else s
            res[key][0] += 1
            try:
                ast.parse(code)
            except IndentationError:
                res[key][1] += 1; res[key][2] += 1
            except SyntaxError:
                res[key][2] += 1
    for k, (n, ie, pe, tags) in res.items():
        print(f"{k:22s} tags={tags:3d} outputs={n:5d} indentation_error={ie:4d} ({ie/n:.1%}) "
              f"unparseable={pe:4d} ({pe/n:.1%})")

if __name__ == "__main__":
    main()
