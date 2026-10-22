#!/usr/bin/env python3
"""Print the quantization type of the embedding/output tensors and the overall type mix per GGUF.

Usage: tensor_types.py LABEL=PATH [...]
"""
import collections, sys

from gguf import GGUFReader

for arg in sys.argv[1:]:
    label, path = arg.split("=", 1)
    t = {x.name: x.tensor_type.name for x in GGUFReader(path).tensors}
    mix = dict(collections.Counter(t.values()))
    print(f"{label:<18} token_embd={t.get('token_embd.weight')}  output={t.get('output.weight', '(tied)')}  "
          f"attn_v.0={t.get('blk.0.attn_v.weight')}  ffn_down.0={t.get('blk.0.ffn_down.weight')}  mix={mix}", flush=True)
