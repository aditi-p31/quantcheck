# quantcheck

Functional acceptance testing for quantized LLM artifacts (GGUF files served
through Ollama), and the full audit dataset behind the paper:

> **Broken on Arrival: Non-Functional Quantized LLM Artifacts in Public Model
> Registries and How to Catch Them.** Aditi Patodiya, 2026.
> [arXiv:2609.05881](https://arxiv.org/abs/2609.05881)

Release `v3.0` of this repository accompanies the revised paper, which
replaces version 1 of the preprint as arXiv version 2. Version 1 had a
different title ("Broken on Arrival: Silently Defective LLM Artifacts in
Public Model Registries and How to Catch Them") and a defect diagnosis that
the revision corrects; see [Corrections from v1](#corrections-from-v1).

## Findings

- **Census.** 327 code-capable artifacts were executed (313 quantized): all
  305 tags at or under 8 GB in 15 model lines of the official Ollama library
  (291 quantized, 14 fp16, in 29 model-and-size groups), and 22 popular
  Hugging Face community files. Each artifact ran a 15-task HumanEval+ screen.
- **Seven non-functional official tags.** Seven tags (2.3%, Wilson 95% CI
  1.1–4.7%) are suspects on the screen and are confirmed on all 164
  HumanEval+ tasks: six solve none and `llama3.2:1b-instruct-q3_K_S` solves
  6. All seven are q2_K to q3_K_L tags of models with at most 4B parameters:
  four `qwen2.5-coder:3b-instruct` tags (q2_K, q3_K_S, q3_K_M, q3_K_L),
  `phi3.5:3.8b-mini-instruct-q2_K`, and two `llama3.2:1b-instruct` tags
  (q2_K, q3_K_S).
- **No file defects.** Five of the seven were rebuilt from the original
  checkpoints with llama.cpp. The four Qwen2.5-Coder-3B tags match our
  uncalibrated rebuild in all 434 tensors; the phi3.5 tag matches in all 197
  tensors once its 32 `attn_qkv` tensors use `Q2_K` (an older llama.cpp type
  mix). Each of the five files is an exact, uncalibrated llama.cpp
  quantization of the released weights. The llama3.2-1B checkpoint is
  licence-gated and was not rebuilt, so its two tags are non-functional but
  unattributed.
- **Calibration rescues most of them.** Adding only an importance matrix
  (imatrix) to the same weights, toolchain and tensor mix takes Qwen q2_K
  from 0 to 106–113 of 164 tasks, q3_K_M to 76–89 and q3_K_L to 80–86. Qwen
  q3_K_S stays weak under every calibration (13–30). For phi3.5, llama.cpp's
  current tensor mix alone lifts the uncalibrated build from 0 to 21, and an
  imatrix to 37; a third-party imatrix build at the tag's own mix scores 34.
- **The recipe alone does not predict failure.** The library's q2_K to
  q3_K_L tags of Qwen2.5-Coder-1.5B are also tensor-identical to our
  uncalibrated rebuild (all 338 tensors) and stay functional (13–15 of 15).
- **Seven is a lower bound.** All 12 deepseek-coder-1.3B tags, fp16
  included, score 1 to 6 of 15, so a group baseline cannot judge them; the
  group is not attributed.
- **The screen.** It missed none of 66 sampled unflagged artifacts (95%
  upper bound 5.5%) and costs about 30 s of generation per tag (median, one
  RTX 4090). A WikiText-2 perplexity threshold, set after the fact, flags
  the five failures we measured.

The paper gives the full method, the attribution rule, and its limits.

## Corrections from v1

- **The v1 defect diagnosis is corrected.** Version 1 reported the four
  Qwen2.5-Coder-3B tags and the phi3.5 q2_K tag as "silently defective"
  conversions. Its referees were chosen by distributor, not by recipe: they
  were importance-matrix builds from bartowski, and for q3_K_S and q3_K_L
  the nearest available level (Q3_K_M) rather than the same one.
  Recipe-matched rebuilds show the five files are exact, uncalibrated
  quantizations. They are still non-functional, but they are not defective
  files.
- **The September 2026 correction was also wrong in part.** On 2026-09-10 the
  phi3.5 claim was withdrawn on ollama/ollama#18252 because a no-imatrix
  upload from lm-kit also failed. That upload carries the library file's
  tensors, so it was not an independent test. The same comment kept the four
  Qwen claims, using Qwen's own GGUF files as no-imatrix referees; those
  files are AWQ-derived, so they are calibrated too. The v3 verdicts rest on
  our own rebuilds.
- **A scoring fault is corrected.** The census scorer marked HumanEval/15 as
  failed for every artifact, although most generations contain the standard
  solution: its strengthened tests can exceed the time limit when scoring runs
  in parallel. Every failed task of every result set was re-evaluated
  serially, one evaluation at a time with the same EvalPlus version and its
  default limits, together with a 3% sample of passes (none changed).
  HumanEval/15 then passes for 275 of the 305 official artifacts, one of which
  also gains HumanEval/23; no pass turns into a fail. Stage-one flags fall from
  50 to 39; the class counts and the seven suspects are unchanged. The original
  score files are left as they were. `rerun-2026-10/census_rescore.jsonl` is an
  earlier parallel rescore; the serial scores the paper reports are in
  `rerun-2026-10/serial/`.
- **Superseded v1 outputs are kept for the record.** `analysis/findings.json`
  (written by `analysis/analyze.py`) still lists five `confirmed_defects`;
  `analysis/classified.json` (from the older ratio rule in
  `analysis/classify.py`) labels five tags `DEFECTIVE`; and the `verdict`
  field in `results*/audit_scored.jsonl` is `"DEFECTIVE"` for every
  artifact below 9 of 15. That field is the raw stage-one flag, not a
  finding. The paper's numbers are in `rerun-2026-10/serial/numbers_serial.json`
  (`rerun-2026-10/analysis/numbers_v3.json` holds the earlier parallel-rescore
  version).
- **Upstream reports.** `disclosure/DISCLOSURES.md` records the original
  report, the withdrawals and their dates.

## What is in this repository

| Path | Contents |
|---|---|
| `harness/` | The census pipeline: pull an artifact, run the smoke suite, record output statistics, score with EvalPlus, delete the model to bound disk use |
| `smoke_suite_v1.json` | The 15 smoke tasks (HumanEval+ task ids) and the tuning record |
| `heldout_49.json` | The 49 other HumanEval+ tasks used for the miss audit |
| `inventory_candidates.json` | The census inventory (327 artifacts) |
| `results/` | Census dataset: per-artifact generation transcripts (361 files), raw results with output statistics, original scores, and the full 164-task runs of the suspects |
| `results-mac/`, `results-metalrep/` | Metal-backend replication runs |
| `results-native/` | Native-template control runs for two community files |
| `results-sensitivity/` | Threshold sensitivity runs (v1) |
| `analysis/` | v1 analysis code and outputs (see Corrections) |
| `metal_replication.json`, `referee_round2.json`, `sensitivity_sample.json` | v1 adjudication and robustness inputs |
| `muse_case_study.json`, `muse-glimmer-tracking/` | Day-zero case study of community conversions of a newly released model (v1) |
| `rerun-2026-10/` | The October 2026 rerun behind the v3 findings: rebuilds, calibration, tensor comparisons, perplexity, robustness and miss-audit runs, the dated run plan, logs, and the v3 analysis scripts (below) |
| `disclosure/DISCLOSURES.md` | Upstream report log |

### The 2026-10 rerun (`rerun-2026-10/`)

The rerun used one RTX 4090 pod with Ollama 0.32.6 (the census version) for
generation and llama.cpp v0.7.0 (`620d222`) on CPU for conversion,
quantization, importance matrices and perplexity. `RUN_PLAN.md` is the dated
local run plan: the decision rule and the first-round runs were written
before any run, and its log records each later addition and its expected
reading before it ran.

| Path | Contents |
|---|---|
| `RUN_PLAN.md` | Dated run plan and run log |
| `fn_sample_30.json`, `fn_sample_b.json` | The two pre-drawn samples of unflagged artifacts for the miss audit (seeds 20261021, 20261022) |
| `results/` | R1, 15 tasks: the five library suspects, their 4-bit siblings, our plain (uncalibrated) rebuilds, third-party imatrix (bartowski) and Qwen AWQ-derived files, and the Q4_K_M/Q6_K positive controls |
| `results-r2/` | R2, generation settings: context 4,096 and 8,192, 2,048-token cap, temperature 0.2 with seeds 1–3, for ten builds |
| `results-r3/`, `results-r3b/` | Miss audit: 29 + 27 unflagged census artifacts on the 49 held-out tasks |
| `results-r5/` | R5, 15 tasks: our own WikiText-2 imatrix builds |
| `results-r6/` | R6, all 164 tasks: calibrated Qwen2.5-Coder-3B builds and controls |
| `results-p0/` | 15 tasks: phi3.5 rebuilt with the library's tensor mix, and code-imatrix builds |
| `results-p0c/` | All 164 tasks: phi3.5 builds, the remaining third-party Qwen builds, code-imatrix Qwen builds |
| `results-g1/` | Qwen2.5-Coder 0.5B and 1.5B at q2_K–q3_K_L: library tag, plain rebuild, own imatrix |
| `census_rescore.jsonl` | Corrected per-task results for the 15 suite tasks of all 334 archived census smoke transcripts |
| `p0b_tensor_compare.jsonl` | Library tag vs plain rebuild, per tensor: Qwen-3B q2_K–q3_K_L and q4_K_M, phi3.5 q2_K |
| `p0f_compare.jsonl` | phi3.5 q2_K library tag vs our rebuild with `attn_qkv` at `Q2_K` |
| `g1_tensor_compare.jsonl` | Qwen 0.5B and 1.5B library tags vs plain rebuilds |
| `local_referee_hashes.jsonl` | File and tensor hashes of locally held third-party files: QuantFactory and lm-kit phi3.5 Q2_K, Qwen's q2_k and q3_k_m |
| `ppl/` | `llama-perplexity` logs (WikiText-2 test, 20 chunks of 512 tokens) |
| `quants-imat/`, `quants-imat-code/`, `quants-g1/` | Importance-matrix files (WikiText-2 train; Python code; WikiText-2 train for 0.5B/1.5B). These are activation statistics in llama.cpp's GGUF imatrix format, not model files |
| `source_commits.jsonl` | Hugging Face revisions of the four source checkpoints |
| `env.txt`, `pip_freeze.txt`, `ollama_tarball.sha256` | Pod environment, Python packages, hash of the Ollama 0.32.6 release archive |
| `calib_sha256.txt`, `calib_code_sha256.txt` | SHA-256 of the two calibration texts (the texts are not included; see below) |
| `logs.tar.xz` | Run logs: Ollama server log, conversion, quantization, imatrix and queue logs (84 MB unpacked) |
| `scripts/` | The pod scripts and run-entry files (see "Rebuild, calibrate and compare") |
| `a1/` | Suite-size analysis: `a1_analysis.py` and `a1_results.json` on the original scores, `A1_REPORT.md`, an independent check in `verify/`, and `a1_rescored.py`/`.json` on the corrected scores |
| `analysis/` | `numbers_v3.py`, `numbers_v3.json` and `figures_v3.py` on the earlier parallel rescore |
| `serial/` | The serial re-scoring the paper reports: `serial_rescore.py`, per-set `*_serial.jsonl` scores, `flips.jsonl`, `instances.jsonl` (one line per serial evaluation, with EvalPlus reasons and timings), `numbers_serial.py`/`.json` (every number in the revised paper), `a1_serial.py`/`.json`, `figures_serial.py`, and the reports `SERIAL_REPORT.md`, `PAPER_DIFF.md`, `VERIFY_REPORT.md` |
| `ds13/` | deepseek-coder-1.3B diagnosis scripts and outputs |

Every results directory has `runs.jsonl` (one record per run: the entry, the
Ollama options, per-task output statistics and, for rebuilds and downloaded
files, a `hash` record with the whole-file SHA-256, the tensor-payload
SHA-256, the tensor count, key metadata and any imatrix keys),
`scored.jsonl` (EvalPlus per-task results; a task passes only when both the
base and the plus tests pass), and `transcripts/<id>__<setting>.jsonl`. Runs
of census tags and already hashed builds were made with `--no-hash`. Some
`(id, setting)` pairs in `scored.jsonl` were scored twice by overlapping
scorer passes with identical results; the analysis uses the last row. Two R1
entries (`plain-qwen3b-F16`, `plain-qwen3b-Q8_0`) have an `error`: Ollama
ran out of local disk while importing them.

The quantized GGUF files themselves (our rebuilds and the downloaded
third-party files) are not distributed; their hashes are in the `runs.jsonl`
`hash` records. Paths inside the records are pod paths: `/workspace/p2rerun/`
corresponds to `rerun-2026-10/`, and `/root/p2/run/` to
`rerun-2026-10/scripts/` together with `harness/`, `smoke_suite_v1.json` and
`heldout_49.json` at the repository root and the two `fn_sample_*.json` files
in `rerun-2026-10/`.

## Reproduce the paper's numbers

The census, attribution, calibration, perplexity, robustness and miss-audit
numbers in the revised paper come from one script, using only the Python
standard library and the serial scores:

```
python3 rerun-2026-10/serial/numbers_serial.py
```

It rewrites `rerun-2026-10/serial/numbers_serial.json`. The screen was tuned on
24 Qwen2.5-Coder configurations from a separate study; their names are in
`serial/tuning_configs.json`, but their per-task results are not in this
release, so the script keeps the committed `tuning_serial` values (the MBPP+
range and the 94% suite figure) and marks them `from_committed_file`. Every
other value is recomputed. The earlier parallel-rescore version of the numbers
is reproduced as described below.

```
python3 rerun-2026-10/analysis/numbers_v3.py
```

(The deepseek-coder-1.3B diagnosis in the paper's RQ1 section, on
unparseable outputs and prompt tokenization, is not computed by this script.
Its scripts and their JSON outputs are in `rerun-2026-10/ds13/`; the census
Ollama `serve.log` they parse is not released, so the per-load records in
`servelog_loads.json` are the released form of that evidence.)

It reads the census files at the repository root (`results/audit_scored.jsonl`,
`results/audit_results.jsonl`, `results/fullrun_scores.jsonl`,
`smoke_suite_v1.json`, and `analysis/analyze.py`, whose grouping helpers it
reuses) and the rerun files in `rerun-2026-10/`, and rewrites
`rerun-2026-10/analysis/numbers_v3.json`. Run on this repository, it
reproduces the committed `numbers_v3.json` byte for byte.

The suite-size analysis (RQ4, "Suite choice"):

```
QUANTCHECK_P1_RESULTS=/path/to/p1-eval-results python3 rerun-2026-10/a1/a1_rescored.py
```

`a1_rescored.py` imports `a1_analysis.py`, first checks that it reproduces
the released `a1_results.json` from the original scores, then recomputes the
suite-size curve on the corrected scores and writes `a1_rescored.json`. Its
last step reruns the calibration-suite check (the "94% of random
15-of-164 suites" figure), which needs the per-task EvalPlus results of the
24 Qwen2.5-Coder tuning configurations (48 `*.samples-sanitized_eval_results.json`
files from an earlier evaluation). Those files are not in this repository.
Without them, the suite-size part runs but the script stops with an
`AssertionError` in `part2_3` and writes nothing. The committed
`a1_rescored.json` was produced with them.

The figures need matplotlib and numpy:

```
python3 rerun-2026-10/analysis/figures_v3.py      # writes rerun-2026-10/figs/
```

**Paths.** These scripts originally pointed at absolute paths on the
author's machine. In this release the defaults follow the repository layout,
and each can be overridden with an environment variable:

| Variable | Default | Used by |
|---|---|---|
| `QUANTCHECK_RERUN_DIR` | `rerun-2026-10/` | `numbers_v3.py`, `figures_v3.py`, `a1_rescored.py` |
| `QUANTCHECK_A1_DIR` | `rerun-2026-10/a1/` | `numbers_v3.py`, `a1_rescored.py` |
| `QUANTCHECK_NUMBERS_JSON` | `rerun-2026-10/analysis/numbers_v3.json` | `a1_rescored.py` |
| `QUANTCHECK_ROOT` | repository root | `a1_analysis.py`, `a1/verify/*.py` |
| `QUANTCHECK_P1_RESULTS` | none in this repository | `a1_analysis.py`, `a1_rescored.py`, `a1/verify/*.py` |

Only those path lines were changed, so the SHA-256 of `a1_analysis.py`
recorded in `a1_rescored.json` refers to the file before this edit. Absolute
paths recorded inside `a1_results.json` and `a1_rescored.json` were replaced
by `<QUANTCHECK_ROOT>`; rerunning the scripts records your own paths there.
`a1/verify/verify_extra.py` also reads the census archive
`results/audit_data_full.tgz`, which is not in this repository (the same
transcripts are in `results/transcripts/`).

The v1 census pipeline still runs as before (`python3 analysis/analyze.py`
rewrites `analysis/findings.json`), but its adjudication is the withdrawn v1
rule.

## Smoke-test an artifact yourself

Requirements: Python 3.9+, [Ollama](https://ollama.com) serving locally (the
study pinned v0.32.6), and [EvalPlus](https://github.com/evalplus/evalplus)
0.3.1, which supplies the task prompts as well as the scorer. A virtual
environment keeps the EvalPlus executables next to the interpreter:

```
python3 -m venv .venv && .venv/bin/pip install evalplus==0.3.1
.venv/bin/python harness/audit.py --only qwen2.5-coder:3b-instruct-q3_K_M --results-dir my-results
.venv/bin/python rerun-2026-10/scripts/rescore_census.py my-results my-results/scored.jsonl 1
```

`harness/audit.py` runs `ollama pull` for each selected inventory entry,
sends the 15 suite tasks to Ollama's `/api/chat` (temperature 0, seed 42,
context 2,048, at most 768 new tokens), and writes the generations to
`<results-dir>/transcripts/` and one record per artifact, with the per-task
output statistics (repeated 6-gram share, prompt echo, whether generation hit
the token cap, presence of a function definition), to
`<results-dir>/audit_results.jsonl`. It then stops and removes the model
(`--keep-model` keeps it). Notes:

- `--only` selects a tag from `inventory_candidates.json`. To test another
  tag, pass `--inventory FILE` with `{"artifacts": [{"tag": "..."}]}`.
- Runs are resumable: tags already in the results directory's
  `audit_results.jsonl` are skipped. Without `--results-dir` the script
  writes to this repository's `results/`, where every census tag is already
  recorded, so nothing runs.
- Entries whose tag starts with `hf:` are skipped; Hugging Face files were
  run with `harness/hf_audit.py` (pod paths) or `rerun-2026-10/scripts/run_entries.py`.
- `--task-file heldout_49.json` runs the 49 miss-audit tasks instead.
- `OLLAMA_BIN` (default `ollama`) and `OLLAMA_HOST` (a full URL, default
  `http://127.0.0.1:11434`) configure the runtime.

Scoring: `rerun-2026-10/scripts/rescore_census.py RESULTS_DIR OUT.jsonl [workers]`
scores every transcript in `RESULTS_DIR` with the EvalPlus executables found
next to the Python interpreter, and writes per-task pass/fail and `n_pass`.
`harness/score_smoke.py`, the census scorer, scores only this repository's
`results/` directory, skips tags already in `results/audit_scored.jsonl`,
and finds EvalPlus through `EVALPLUS_BIN` (default `~/Library/Python/3.9/bin`).
HumanEval/15's strengthened tests are slow and can exceed EvalPlus's time
limit when scoring runs in parallel, so use one worker; scores are lower
bounds.

Reading the score: on the tuning set every healthy configuration passes 15
of 15. The screen flags an artifact below 9 of 15 (stage one), then compares
it with its group baseline, the median score of the same model and size at
q6_K, q8_0 or fp16 (stage two). A suspect scores at most 2 of 15 in a group
whose baseline is at least 8; the census baselines are in
`results/audit_scored.jsonl` (corrected by `rerun-2026-10/census_rescore.jsonl`).
A low score says an artifact does not work, not why. Attributing a cause
needs the rebuild comparison below.

## Rebuild, calibrate and compare

`rerun-2026-10/scripts/` holds the scripts exactly as they ran on the pod.
They hardcode pod paths (`/root/p2`, `/root/p2/run`, `/workspace/p2rerun`,
Ollama at `/root/p2/ollama/bin/ollama`); adjust these before reuse. The
underlying steps, with llama.cpp v0.7.0:

```
python llama.cpp/convert_hf_to_gguf.py CHECKPOINT_DIR --outtype f16 --outfile model-f16.gguf
llama-quantize model-f16.gguf model-Q3_K_M.gguf Q3_K_M                       # plain rebuild, no calibration
llama-imatrix -m model-f16.gguf -f wiki.train.raw -o model.imatrix --chunks 100 -c 512 -t 12
llama-quantize --imatrix model.imatrix model-f16.gguf model-imat-Q3_K_M.gguf Q3_K_M
llama-quantize --tensor-type attn_qkv=q2_k phi35-f16.gguf phi35-Q2_K-libmix.gguf Q2_K   # phi3.5 with the library's older mix
llama-perplexity -m model.gguf -f wikitext-2-raw/wiki.test.raw --chunks 20 -c 512 -t 12
```

The GGUF behind an Ollama tag is the `FROM .../blobs/...` path printed by
`ollama show --modelfile TAG`. The comparison scripts need the `gguf` Python
package (`pip install gguf`, or `llama.cpp/gguf-py`):

- `compare_tensors.py A=PATH_A B=PATH_B` compares two GGUF files tensor by
  tensor (type, shape and bytes, independent of tensor order) and lists the
  metadata keys that differ. The paper's tensor-identity results use it.
- `gguf_hash.py LABEL=PATH` prints the whole-file SHA-256 and a tensor-payload
  SHA-256 over the tensors in file order. Because it depends on tensor order,
  it first reported every plain rebuild as distinct; the order-independent
  comparison is the one reported. `gguf_tensor_hash_stdlib.py` computes the
  same hashes without the `gguf` package (used for `local_referee_hashes.jsonl`).
- `tensor_types.py LABEL=PATH` prints the tensor type mix.
- `run_entries.py ENTRIES.json --setting NAME [--options JSON] [--tasks suite|FILE] --results-dir DIR`
  runs library tags, local GGUF files and Hugging Face files through the
  census generation path, copying the chat template from a donor library tag;
  `score_runs.py DIR [workers]` scores the results. Run them with
  `PYTHONPATH=harness` so `run_entries.py` finds `harness/audit.py`, and set
  `OLLAMA_BIN`; the script writes Modelfiles to `/root` and downloads to
  `/root/hfdl`.

Run order on the pod: `setup_pod.sh`; `r1.sh` (starts Ollama with
`start_ollama.sh`, builds the plain rebuilds with `quantize_refs.sh`, runs
R1); `pc.sh` (positive controls); `r2_r3.sh` (R2 only; its R3 part was
handed to `gpu_queue.sh`); `imatrix_refs.sh` and
`p0_cpu.sh` on CPU (importance matrices, the phi3.5 library-mix rebuild and
its tensor comparison, code calibration, perplexity); `gpu_queue.sh` (R3,
R5, R6, R3b, then `gpu_queue_more.sh`: retries, P0 smoke, P0-c) with
`scorer_loop.sh` scoring alongside; `g1lite.sh`; and `rescore_census.py` for
the census rescore. `queue_tail.sh` was superseded by `gpu_queue.sh` and its
log is empty. The library-vs-plain comparison in `p0b_tensor_compare.jsonl` was
run by calling `compare_tensors.py` directly.

### Calibration texts (not included)

The calibration texts are not redistributed. To rebuild them, check each
against its recorded SHA-256:

- **WikiText-2** (Merity et al., 2017; CC BY-SA): the raw v1 archive that
  `imatrix_refs.sh` downloads from
  `https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip`.
  `wikitext-2-raw/wiki.train.raw` is the imatrix text
  (`calib_sha256.txt`); `wiki.test.raw` is the perplexity text (its hash was
  not recorded).
- **Python code**: the first 1,500,000 bytes of the `.py` files under 200 KB
  in llama.cpp v0.7.0 (`620d2225cc436ab0b001e3200e590e3b286ef9ab`),
  concatenated in sorted path order, as in `p0_cpu.sh`:
  `find llama.cpp -name "*.py" -size -200k | sort | xargs cat | head -c 1500000 > code.txt`
  (`calib_code_sha256.txt`). Sort order depends on the locale; if the hash
  differs, try `LC_ALL=C`.

## Data notes

- `inventory_candidates.json` carries `"frozen": false`. The inventory was
  nevertheless fixed on 2026-08-10 (its `generated` field) before the census
  ran on 2026-08-12 (`ts_start` in `results/audit_results.jsonl`, 00:59 to
  08:39 UTC for the official tags); the flag was never switched, and the
  file is unchanged since. Each artifact's pull time is in
  `results/audit_results.jsonl` (`pull_s`).
- Three v1 transcripts contained email addresses that a model reproduced
  from its training data (`results-native/transcripts/deepseek-coder-6.7b-instruct.Q3_K_M.native.jsonl`,
  `...Q4_K_M.native.jsonl`, and
  `results/transcripts/hf_TheBloke_deepseek-coder-6.7B-instruct-GGUF_deepseek-coder-6.7b-instruct.Q4_K_M.gguf.jsonl`).
  In v3 they are replaced by `<EMAIL_REDACTED>`. Only the contents of string
  literals changed, so scores are unaffected.
- In `rerun-2026-10/logs.tar.xz`, the public key that Ollama generated for
  the pod at start-up is replaced by `<OLLAMA_PUBLIC_KEY_REDACTED>`, and
  `RUN_PLAN.md` names the pod's storage volume `<RUNPOD_VOLUME>`.

## Upstream disclosure

The five tags were reported in
[ollama/ollama#18252](https://github.com/ollama/ollama/issues/18252). The
report, its corrections and the withdrawal of the v1 defect claims are
tracked in `disclosure/DISCLOSURES.md`.

## License

Code is released under the MIT License (see `LICENSE`). The audit dataset
(everything under `results*/`, the data files in `rerun-2026-10/`, and the
top-level JSON data files) is released under CC BY 4.0. The calibration
texts are not included.

## Citing

```bibtex
@article{patodiya2026brokenonarrival,
  title   = {Broken on Arrival: Non-Functional Quantized {LLM} Artifacts in
             Public Model Registries and How to Catch Them},
  author  = {Patodiya, Aditi},
  journal = {arXiv preprint arXiv:2609.05881},
  year    = {2026},
  doi     = {10.48550/arXiv.2609.05881},
  url     = {https://arxiv.org/abs/2609.05881}
}
```

GitHub's "Cite this repository" button (from `CITATION.cff`) emits the same
citation in BibTeX and APA. If quantcheck catches a broken artifact for you,
an issue report here is welcome.
