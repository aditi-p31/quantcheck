#!/usr/bin/env python3
"""Per-artifact file digests of the August 2026 census, extracted from the census Ollama serve.log.

The census serve.log (93 MB, CUDA pod, 2026-08-12) is not part of this release. This script records
the part of it that identifies which file each census artifact ran on, and writes census_digests.json
next to this file:

  server                      Ollama version, bundled llama.cpp build, GPU, compute library and driver
                              from the log header.
  artifacts[tag]              one entry per scored census artifact (results/audit_scored.jsonl):
    official tags             the model blob loaded ("using llama-server for model") inside the tag's
                              run window [ts_start - 1 s, ts_end + 1 s]. A registry blob name is the
                              SHA-256 of the GGUF file, so blob_sha256 is the file hash.
    Hugging Face files        imported with `ollama create`: file_sha256 is the blob the file was
                              uploaded as ("quantizing model type=COPY input=...", i.e. the SHA-256 of
                              the downloaded file); loaded_blob_sha256 is Ollama's re-written copy.
    serve_log_line            line number of the record used, file_type as llama.cpp printed it.
  template_selection_blobs    for each official tag, every blob loaded before a "template selection"
                              line naming the tag (the input of the blob check in numbers_regroup.py).

Run windows come from the census run records (results/audit_results.jsonl). Every window must hold
exactly one load (official) or one import (Hugging Face); the script asserts this.

Usage: python3 census_digests.py SERVE_LOG [RUNS.jsonl ...]   (default RUNS: results/audit_results.jsonl)
Standard library only.
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TS = re.compile(r"^time=(\S+) ")
LOAD = re.compile(r'msg="loading model via llama-server" model=\S*/blobs/(sha256-[0-9a-f]+)')
TSEL = re.compile(r'msg="template selection" model=registry\.ollama\.ai/library/(\S+)')


def ts_of(line):
    return datetime.datetime.fromisoformat(TS.match(line).group(1).replace("Z", "+00:00")).timestamp()


def parse(path):
    loads, copies, header, tsel = [], [], {}, {}
    cur, last = None, None
    for i, line in enumerate(open(path, errors="replace"), 1):
        if "Listening on" in line and "version" in line and "ollama_version" not in header:
            header["ollama_version"] = re.search(r"version ([0-9.]+)", line).group(1)
        if "inference compute" in line and "gpu" not in header:
            header["gpu"] = re.search(r'description="([^"]+)"', line).group(1)
            header["library"] = re.search(r"library=(\S+)", line).group(1)
            header["driver"] = re.search(r"driver=(\S+)", line).group(1)
        if "llama_cpp_build" not in header:
            m = re.search(r"build[ =:]+1 \(([0-9a-f]+)\)", line)
            if m:
                header["llama_cpp_build"] = m.group(1)
        a = LOAD.search(line)
        if a:
            last = a.group(1)
        b = TSEL.search(line)
        if b and last:
            tsel.setdefault(b.group(1), set()).add(last)
        if "using llama-server for model" in line:
            cur = {"ts": ts_of(line), "blob": re.search(r"sha256-([0-9a-f]{64})", line).group(1), "line": i,
                   "file_type": None}
            loads.append(cur)
        elif 'msg="quantizing model" type=COPY' in line:
            copies.append({"ts": ts_of(line), "blob": re.search(r"input=\S*sha256-([0-9a-f]{64})", line).group(1),
                           "line": i})
        elif cur is not None and cur["file_type"] is None and "print_info: file type" in line:
            cur["file_type"] = line.split("=", 1)[1].strip()
    return loads, copies, header, tsel


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: census_digests.py SERVE_LOG [RUNS.jsonl ...]  (the census serve.log is not released)")
    log = sys.argv[1]
    runs_files = sys.argv[2:] or [os.path.join(ROOT, "results", "audit_results.jsonl")]
    loads, copies, header, tsel = parse(log)
    scored = [json.loads(l) for l in open(os.path.join(ROOT, "results", "audit_scored.jsonl")) if l.strip()]
    runs = {}
    for f in runs_files:
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                if r.get("ts_end") and r.get("transcript"):
                    runs.setdefault(r["tag"], r)        # first completed run of each tag
    arts = {}
    for s in scored:
        tag, r = s["tag"], runs[s["tag"]]
        lo, hi = r["ts_start"] - 1, r["ts_end"] + 1
        w = [l for l in loads if lo <= l["ts"] <= hi]
        assert len(w) == 1, (tag, len(w))
        e = {"channel": s["channel"], "run_window_utc": [r["ts_start"], r["ts_end"]], "file_type": w[0]["file_type"]}
        if s["channel"] == "ollama-official":
            e.update(blob_sha256=w[0]["blob"], serve_log_line=w[0]["line"])
        else:
            c = [x for x in copies if lo <= x["ts"] <= hi]
            assert len(c) == 1, (tag, len(c))
            e.update(file_sha256=c[0]["blob"], serve_log_line=c[0]["line"], loaded_blob_sha256=w[0]["blob"],
                     loaded_serve_log_line=w[0]["line"])
        arts[tag] = e
    official = [s["tag"] for s in scored if s["channel"] == "ollama-official"]
    out = {
        "source": "census Ollama serve.log, CUDA pod, 2026-08-12 (not released; extracted with census_digests.py)",
        "server": header,
        "n_artifacts": len(arts),
        "artifacts": arts,
        "template_selection_blobs": {t: sorted(tsel.get(t, ())) for t in official},
    }
    with open(os.path.join(HERE, "census_digests.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=False)
    print(json.dumps(header), len(arts), "artifacts")


if __name__ == "__main__":
    main()
