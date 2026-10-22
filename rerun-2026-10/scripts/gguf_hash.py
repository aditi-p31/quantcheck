#!/usr/bin/env python3
"""Hash GGUF files two ways: the whole file, and the tensor payload only.

The tensor hash covers each tensor's name, shape, type and raw bytes in file order and ignores
metadata keys. Two files with the same tensor hash carry the same weights, whatever their
metadata says, so they cannot referee each other.

Usage: gguf_hash.py LABEL=PATH [LABEL=PATH ...] > hashes.jsonl
"""
import hashlib, json, sys

from gguf import GGUFReader

KEYS = ("general.name", "general.finetune", "general.file_type", "general.quantization_version")


def kv_value(field):
    try:
        if field.types and field.types[0].name == "STRING":
            return bytes(field.parts[field.data[0]]).decode("utf-8", "replace")
        return field.parts[field.data[0]].tolist()[0]
    except Exception:
        return None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(label, path):
    r = GGUFReader(path)
    th = hashlib.sha256()
    for t in r.tensors:
        th.update(t.name.encode())
        th.update(json.dumps([int(x) for x in t.shape]).encode())
        th.update(str(int(t.tensor_type)).encode())
        th.update(t.data.tobytes())
    meta = {k: kv_value(r.fields[k]) for k in KEYS if k in r.fields}
    imatrix_keys = sorted(k for k in r.fields if "imatrix" in k.lower())
    return {"label": label, "path": path, "file_sha256": file_sha256(path),
            "tensor_sha256": th.hexdigest(), "n_tensors": len(r.tensors),
            "n_kv": len(r.fields), "meta": meta, "imatrix_keys": imatrix_keys}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        print(json.dumps(describe(label, path)), flush=True)
