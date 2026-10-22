#!/usr/bin/env python3
"""F05 diagnosis, step 0: per model load in the census serve.log (extracted to
gates/ds13/logs/serve.log from results/audit_data_full.tgz), record the
llama-server model name, layer count, file type, pre-tokenizer status and the
prompt token count of each request. Writes gates/ds13/servelog_loads.json and
prints the loads whose pre-tokenizer is missing.
"""
import collections, json, os, re

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(V3, "gates", "ds13", "logs", "serve.log")

def main():
    loads, cur = [], None
    with open(LOG, errors="replace") as f:
        for line in f:
            if "starting llama-server" in line:
                m = re.search(r"--model (\S+)", line)
                cur = {"ts": line.split()[0][5:], "blob": m.group(1)[-12:] if m else None,
                       "name": None, "layers": None, "ftype": None,
                       "pretok": "present", "n_prompt": [], "srv_meta": False}
                loads.append(cur)
                continue
            if cur is None:
                continue
            if "srv    load_model: loading model" in line:
                cur["srv_meta"] = True
            if "load_tensors:" in line:
                cur["srv_meta"] = False   # server's own metadata dump is over
            if cur["srv_meta"] and cur["name"] is None and "general.name str" in line:
                cur["name"] = line.split("=", 1)[1].strip()
            m = re.search(r"\.block_count u32\s+=\s+(\d+)", line)
            if cur["srv_meta"] and m and cur["layers"] is None:
                cur["layers"] = int(m.group(1))
            if cur["srv_meta"] and "print_info: file type" in line and cur["ftype"] is None:
                cur["ftype"] = line.split("=", 1)[1].strip()
            if cur["srv_meta"] and "missing pre-tokenizer type" in line:
                cur["pretok"] = "MISSING (default used)"
            m = re.search(r"tokenizer\.ggml\.pre str\s+=\s+(\S+)", line)
            if cur["srv_meta"] and m:
                cur["pretok"] = m.group(1)
            m = re.search(r"new prompt, .*task\.n_tokens = (\d+)", line)
            if m:
                cur["n_prompt"].append(int(m.group(1)))
    for l in loads:
        l.pop("srv_meta", None)
    json.dump(loads, open(os.path.join(V3, "gates", "ds13", "servelog_loads.json"), "w"), indent=0)
    miss = [l for l in loads if l["pretok"].startswith("MISSING")]
    print("loads:", len(loads), " missing pre-tokenizer:", len(miss))
    c = collections.Counter((l["name"], l["layers"]) for l in miss)
    for k, v in c.items():
        print(f"  {v:3d}  {k[0]}  layers={k[1]}")
    print("first-15 prompt lengths per deepseek-coder load (name, layers, type):")
    seen = collections.Counter()
    for l in loads:
        if l["name"] and "deepseek-ai" in l["name"]:
            key = tuple(l["n_prompt"][:15])
            seen[(l["name"], l["layers"], key)] += 1
    for (n, ly, key), v in seen.items():
        print(f"  x{v:2d} {n} layers={ly}: {list(key)}")

if __name__ == "__main__":
    main()
