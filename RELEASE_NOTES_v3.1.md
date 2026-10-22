# quantcheck v3.1

v3.1 keeps every data file of v3.0 and updates the analysis behind the paper
"Broken on Arrival: Non-Functional Quantized LLM Artifacts in Public Model
Registries and How to Catch Them". The analysis scripts now run from a clean
checkout, and the release documents where each provenance statement of the
paper is recorded.

## Changes to results

- **Baseline groups by model variant.** Stage two of the screen compares a
  tag with the median score of its group's q6_K, q8_0 and fp16 tags. v3.0
  formed the groups with `size_key` in `analysis/analyze.py`, which pooled
  different registry checkpoints in 5 of its 28 groups (granite 8B,
  granite-code 3B and 20B, codegemma 7B, mistral 7B). v3.1 groups by the
  registry tag without its quantization suffix: 35 groups, the columns of the
  census figure.
- **Class counts** become 271 healthy, 2 degraded, 6 low baseline, 7 suspect
  and 19 no baseline (v3.0: 271/3/6/7/18).
  `mistral:7b-instruct-v0.2-q8_0` moves from degraded to healthy and
  `granite-code:8b-instruct-128k-q4_0` from healthy to no baseline.
- **Unchanged:** the seven suspects and their 164-task scores, the 39
  stage-one flags, the attribution, calibration, perplexity, settings and
  miss-audit results, the screen cost, and every suite-size (A1) value the
  paper quotes.
- **Incident share:** 3 of 35 model variants (8.6%, Wilson 95% interval
  3.0–22.4%), or 3 of 29 registry model-and-size groups (10.3%, 3.6–26.4%)
  as before.
- **Scoring correction:** with the new groups the HumanEval/15 correction
  moves one tag, `yi-coder:1.5b-chat-q2_K`, from degraded to healthy. The
  suspects are unchanged, as before.

## Added

- `rerun-2026-10/serial/numbers_regroup.py`, `.json`: every number in the
  paper, with model-variant baselines. Under the v3.0 grouping it reproduces
  the class counts, suspects and flags of `numbers_serial.json` and
  `numbers_v3.json` (asserted).
- `rerun-2026-10/serial/a1_regroup.py`, `.json`: the suite-size analysis with
  model-variant baselines, every subset of 3 to 15 suite tasks enumerated,
  compared value by value with `a1_serial.json`.
- `rerun-2026-10/serial/census_digests.py`, `.json`: the SHA-256 of the file
  each of the 334 census artifacts ran on, with the server version and log
  line, extracted from the census Ollama server log (the log itself is not
  released).
- `rerun-2026-10/miss_audit/certificates.csv`, `.json`: for each of the 66
  artifacts of the miss audit, the evidence that it solves at least 17 of the
  164 HumanEval+ tasks, combined only within one file digest and one backend.
  All 66 are certified: 50 on the 49-task audit run alone, 14 by census
  screen plus audit on the same file digest and backend, and 2 by a full
  164-task rerun on the census file (next item).
- `rerun-2026-10/results-v1cases/`, `rerun-2026-10/miss_audit/closure_v1cases.json`,
  `rerun-2026-10/scripts/v1cases.sh` and `score_v1cases_serial.py`: the
  miss-audit closure. The first-version audit run of
  `granite-code:3b-instruct-q3_K_M` and `mistral:7b-instruct-q3_K_S` recorded
  neither its backend nor its file digest, so it could not be combined with
  the screen. On 22 October 2026 both tags were rerun on all 164 HumanEval+
  tasks on CUDA (a third RTX 4090 pod, Ollama 0.32.6, census options), each
  loading its census file digest; scored serially, they solve 65 and 44 of
  164. The `closure` column of `certificates.csv` and `.json`, added after
  the rerun, records this; their `status` column keeps its pre-rerun value.
- `PROVENANCE.md`: each provenance statement of the paper mapped to the file
  and record that supports it, or marked as external or not released.

## Fixes

- `rerun-2026-10/serial/numbers_serial.py` read `a1_results.json` from a path
  on the author's machine; it now reads it from `rerun-2026-10/a1/`
  (`QUANTCHECK_A1_DIR`).
- `rerun-2026-10/serial/serial_rescore.py` defaults follow the repository
  layout (`QUANTCHECK_ROOT`, `QUANTCHECK_RERUN_DIR`, `QUANTCHECK_P1_RESULTS`).
- `rerun-2026-10/ds13/`: inputs and outputs are configurable
  (`QUANTCHECK_CENSUS_TRANSCRIPTS`, `QUANTCHECK_CENSUS_SERVELOG`,
  `QUANTCHECK_DS13_DIR`, `QUANTCHECK_DS13_TOKENIZER`, `QUANTCHECK_OUT_DIR`);
  `ds13_census_parse.py` now runs from the release; `ds13_outputs.py` starts
  with its shebang line.
- `analysis/score_experiments.py` honours `EVALPLUS_BIN`.
- README: the current command sequence, the withheld inputs, the miss-audit
  certificates and the path variables.

## Reproduce

```
python3 rerun-2026-10/serial/numbers_regroup.py
python3 rerun-2026-10/serial/a1_regroup.py
python3 rerun-2026-10/serial/figures_serial.py    # needs matplotlib and numpy
```

The per-task results of the 24 screen-tuning configurations belong to a
separate study and are not released. Without them the scripts copy the
tuning-derived values (the MBPP+ range of the tuning set, the 39-task pool,
and the "94% of random 15-of-164 suites" figure) from the committed outputs
and mark them `from_committed_file`; these values are inherited, not
recomputed. Every other value is recomputed from the release.

## Not in this release

The quantized GGUF files and source checkpoints (identified by hash and
revision), the calibration texts (identified by hash), the census and Mac
Ollama server logs (their relevant records are in `census_digests.json`,
`ds13/servelog_loads.json` and `certificates.json`), and the per-task results
of the screen-tuning configurations.
