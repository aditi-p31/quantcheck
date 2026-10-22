#!/usr/bin/env python3
"""F05 diagnosis, step 1: reproduce the census prompt token counts logged by
llama-server (serve.log) for deepseek-coder-1.3b, under (a) the model's own
deepseek-coder pre-tokenizer (HF tokenizer.json) and (b) an emulation of
llama.cpp's 'default' BPE pre-tokenizer, which serve.log says was used
("missing pre-tokenizer type, using: 'default'"). No model is run.
Paths (release): inputs and outputs follow the repository layout and can be overridden with
environment variables; see the README section on rerun-2026-10/ds13/.
QUANTCHECK_DS13_TOKENIZER gives the path of deepseek-coder-1.3b-instruct's tokenizer.json
(default: the Hugging Face hub cache); output goes next to this script (QUANTCHECK_OUT_DIR).
"""
import glob, json, os, sys
from tokenizers import Tokenizer, pre_tokenizers, Regex
from evalplus.data import get_human_eval_plus

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
ROOT = os.path.dirname(V3)
SUITE = json.load(open(os.path.join(ROOT, "smoke_suite_v1.json")))["suite_tasks"]
TOKJ = os.environ.get("QUANTCHECK_DS13_TOKENIZER") or glob.glob(os.path.expanduser(
    "~/.cache/huggingface/hub/models--deepseek-ai--deepseek-coder-1.3b-instruct/snapshots/*/tokenizer.json"))[0]
OUT_DIR = os.environ.get("QUANTCHECK_OUT_DIR", HERE)
INSTRUCTION = ("Please provide a self-contained Python script that solves the following "
               "problem in a markdown code block:")
SYSTEM = ("You are an AI programming assistant, utilizing the Deepseek Coder model, developed by "
          "Deepseek Company, and you only answer questions related to computer science. For "
          "politically sensitive questions, security and privacy issues, and other non-computer "
          "science questions, you will refuse to answer")
# Logged task.n_tokens (serve.log), census order = SUITE order
LOG_OLLAMA = [344, 192, 215, 178, 352, 242, 220, 195, 206, 196, 235, 148, 170, 207, 228]
LOG_THEBLOKE = [285, 133, 156, 119, 293, 183, 161, 136, 147, 137, 176, 89, 111, 148, 169]

def render(system, content):
    # Ollama legacy template blob (59 B): "{{ .System }}\n### Instruction:\n{{ .Prompt }}\n### Response:\n"
    return f"{system}\n### Instruction:\n{content}\n### Response:\n"

def main():
    tasks = get_human_eval_plus()
    correct = Tokenizer.from_file(TOKJ)
    default = Tokenizer.from_file(TOKJ)
    # llama.cpp llm_tokenizer_bpe, LLAMA_VOCAB_PRE_TYPE_DEFAULT regex list, applied in sequence,
    # keeping matches and gaps as separate pieces (== HF Split behavior "isolated").
    exprs = [r"[\p{P}\$\+<=>\^~\|]+",
             r"'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+",
             r"\p{N}+",
             r"[0-9][0-9][0-9]"]
    default.pre_tokenizer = pre_tokenizers.Sequence(
        [pre_tokenizers.Split(Regex(e), behavior="isolated") for e in exprs]
        + [pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)])
    print("system prompt bytes:", len(SYSTEM.encode()), " tokens:", len(correct.encode(SYSTEM, add_special_tokens=False).ids))
    rows = []
    for i, tid in enumerate(SUITE):
        content = f"{INSTRUCTION}\n```python\n{tasks[tid]['prompt']}\n```\n"
        # Ollama tags: 297-B system blob = SYSTEM + "." (296 + 1 B); referee: TEMPLATE copied, no SYSTEM
        for label, sysmsg, logged in (("ollama", SYSTEM + ".", LOG_OLLAMA[i]), ("thebloke", "", LOG_THEBLOKE[i])):
            text = render(sysmsg, content)
            c = correct.encode(text, add_special_tokens=False).ids
            d = default.encode(text, add_special_tokens=False).ids
            # position-wise disagreement in the content part
            import difflib
            sm = difflib.SequenceMatcher(a=c, b=d, autojunk=False)
            same = sum(b.size for b in sm.get_matching_blocks())
            ndiff = sum(max(a1 - a0, b1 - b0) for op, a0, a1, b0, b1 in sm.get_opcodes() if op != "equal")
            rows.append({"task": tid, "cond": label, "logged": logged,
                         "correct_pretok": 1 + len(c), "default_pretok": 1 + len(d),
                         "positions_differing": ndiff})
    for r in rows:
        print(json.dumps(r))
    for label in ("ollama", "thebloke"):
        rr = [r for r in rows if r["cond"] == label]
        od = sorted({r["logged"] - r["default_pretok"] for r in rr})
        oc = sorted({r["logged"] - r["correct_pretok"] for r in rr})
        print(label, "logged-minus-emulated offsets: default", od, " correct", oc,
              " positions differing", sum(r["positions_differing"] for r in rr), "of", sum(r["correct_pretok"] for r in rr))
        print(label, "match default:", sum(r["logged"] == r["default_pretok"] for r in rr), "/", len(rr),
              " match correct:", sum(r["logged"] == r["correct_pretok"] for r in rr), "/", len(rr),
              " sum logged", sum(r["logged"] for r in rr), " sum correct", sum(r["correct_pretok"] for r in rr),
              " sum default", sum(r["default_pretok"] for r in rr))
    json.dump(rows, open(os.path.join(OUT_DIR, "tokcheck.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
