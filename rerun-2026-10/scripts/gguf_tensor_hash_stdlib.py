#!/usr/bin/env python3
"""Stdlib re-implementation of rerun-2026-10/scripts/gguf_hash.py (no gguf package needed).

Tensor hash = sha256 over, for each tensor in file order: name bytes, json.dumps(ne dims as ints),
str(ggml type id), raw tensor bytes. Same definition as gguf_hash.py (GGUFReader: shape = raw dims,
data.tobytes() = raw bytes). Validate by reproducing a tensor hash recorded in R1 runs.jsonl.

Usage: python3 -I gguf_tensor_hash_stdlib.py LABEL=PATH [...]
"""
import hashlib, json, struct, sys

# ggml type id -> (block elements, bytes per block)
SIZES = {0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24), 8: (32, 34),
         9: (32, 36), 10: (256, 84), 11: (256, 110), 12: (256, 144), 13: (256, 176),
         14: (256, 210), 15: (256, 292), 30: (1, 2)}
KEYS = ("general.name", "general.finetune", "general.file_type", "general.quantization_version")


class R:
    def __init__(self, f):
        self.f = f

    def u(self, fmt):
        n = struct.calcsize(fmt)
        return struct.unpack("<" + fmt, self.f.read(n))[0]

    def s(self):
        n = self.u("Q")
        return self.f.read(n).decode("utf-8", "replace")

    def val(self, t):
        scal = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
        if t in scal:
            return self.u(scal[t])
        if t == 8:
            return self.s()
        if t == 9:
            at = self.u("I"); n = self.u("Q")
            return [self.val(at) for _ in range(n)] if n < 64 else (self.skip_arr(at, n) or "<array>")
        raise ValueError(f"bad kv type {t}")

    def skip_arr(self, at, n):
        for _ in range(n):
            self.val(at)
        return None


def describe(label, path):
    with open(path, "rb") as fh:
        r = R(fh)
        assert fh.read(4) == b"GGUF"
        ver = r.u("I"); nt = r.u("Q"); nkv = r.u("Q")
        kv = {}
        for _ in range(nkv):
            k = r.s(); t = r.u("I"); kv[k] = r.val(t)
        infos = []
        for _ in range(nt):
            name = r.s(); nd = r.u("I"); dims = [r.u("Q") for _ in range(nd)]
            typ = r.u("I"); off = r.u("Q")
            infos.append((name, dims, typ, off))
        align = int(kv.get("general.alignment", 32))
        pos = fh.tell()
        start = (pos + align - 1) // align * align
        th = hashlib.sha256()
        for name, dims, typ, off in infos:
            ne = 1
            for d in dims:
                ne *= d
            be, bb = SIZES[typ]
            nbytes = ne * bb // be
            fh.seek(start + off)
            th.update(name.encode())
            th.update(json.dumps([int(x) for x in dims]).encode())
            th.update(str(int(typ)).encode())
            th.update(fh.read(nbytes))
    fs = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            fs.update(chunk)
    return {"label": label, "file_sha256": fs.hexdigest(), "tensor_sha256": th.hexdigest(),
            "gguf_version": ver, "n_tensors": nt, "n_kv": nkv,
            "meta": {k: kv[k] for k in KEYS if k in kv},
            "imatrix_keys": sorted(k for k in kv if "imatrix" in k.lower()),
            "extra_keys_vs_std": sorted(k for k in kv if not k.startswith(("general.", "tokenizer.", "phi3.", "qwen2.", "quantize.")))}


if __name__ == "__main__":
    for a in sys.argv[1:]:
        lab, p = a.split("=", 1)
        print(json.dumps(describe(lab, p)), flush=True)
