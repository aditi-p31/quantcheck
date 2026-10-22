#!/usr/bin/env python3
"""P0-b: order-independent tensor comparison between two GGUF files, plus a metadata diff.

For each tensor name: same type? same shape? same bytes? Reports counts and the differing names,
so "different whole-file hash" can be split into layout, metadata, or weights.

Usage: compare_tensors.py LABEL_A=PATH_A LABEL_B=PATH_B [...more pairs as A,B,A,B]
"""
import hashlib, json, sys

from gguf import GGUFReader


def tensor_map(path):
    r = GGUFReader(path)
    m = {}
    for t in r.tensors:
        m[t.name] = (int(t.tensor_type), tuple(int(x) for x in t.shape),
                     hashlib.sha256(t.data.tobytes()).hexdigest())
    kv = {}
    for k, f in r.fields.items():
        if k.startswith("GGUF.") or k.startswith("tokenizer.ggml.tokens") or k.startswith("tokenizer.ggml.merges"):
            continue
        try:
            v = f.parts[f.data[0]]
            v = bytes(v).decode("utf-8", "replace") if f.types and f.types[0].name == "STRING" else v.tolist()
        except Exception:
            v = None
        kv[k] = v
    return m, kv


def compare(la, pa, lb, pb):
    ma, ka = tensor_map(pa)
    mb, kb = tensor_map(pb)
    names = sorted(set(ma) | set(mb))
    same_bytes = [n for n in names if n in ma and n in mb and ma[n] == mb[n]]
    type_diff = [n for n in names if n in ma and n in mb and ma[n][0] != mb[n][0]]
    data_diff = [n for n in names if n in ma and n in mb and ma[n][0] == mb[n][0] and ma[n][2] != mb[n][2]]
    only = [n for n in names if (n in ma) != (n in mb)]
    kv_diff = {k: (ka.get(k), kb.get(k)) for k in sorted(set(ka) | set(kb)) if str(ka.get(k)) != str(kb.get(k))}
    return {"a": la, "b": lb, "n_tensors": [len(ma), len(mb)], "identical_tensors": len(same_bytes),
            "type_differs": len(type_diff), "same_type_bytes_differ": len(data_diff), "only_in_one": only,
            "type_diff_examples": [(n, ma[n][0], mb[n][0]) for n in type_diff[:12]],
            "data_diff_examples": data_diff[:12],
            "kv_diff": {k: [str(v[0])[:80], str(v[1])[:80]] for k, v in list(kv_diff.items())[:40]}}


if __name__ == "__main__":
    args = sys.argv[1:]
    for i in range(0, len(args), 2):
        la, pa = args[i].split("=", 1)
        lb, pb = args[i + 1].split("=", 1)
        print(json.dumps(compare(la, pa, lb, pb)), flush=True)
