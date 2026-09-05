# quantcheck

Functional acceptance testing for quantized LLM artifacts, and the full audit
dataset behind the paper:

> **Broken on Arrival: Silently Defective LLM Artifacts in Public Model
> Registries and How to Catch Them.** Aditi Patodiya, 2026. Under review.
> arXiv link will be added on announcement.

A quantized model file can download cleanly, load cleanly, and stream fluent
text at normal speed while being completely unable to do its job. Nothing in
the pull-and-run experience reveals this. We executed 327 quantized
code-capable artifacts from public registries under a calibrated 15-task
smoke suite and confirmed five silently defective artifacts, all in the
official library channel. Every verdict was earned against family baselines,
a second GPU backend, and an independent distributor's conversion of the same
model.

## What is in this repository

| Path | Contents |
|---|---|
| `harness/` | The census pipeline: pull an artifact, run the smoke suite, extract degeneration features, score with EvalPlus, delete the model to bound disk use |
| `smoke_suite_v1.json` | The 15 calibrated smoke tasks (HumanEval+ subset) with the calibration record |
| `analysis/` | Analysis code and its outputs; `analyze.py` regenerates `findings.json`, the source of every number in the paper |
| `results/` | The full audit dataset: per-artifact generation transcripts (361 files), scored results, and extracted features |
| `results-mac/`, `results-metalrep/` | Metal-backend replication runs behind the dual-backend defect rule |
| `results-native/` | Native-template control runs |
| `results-sensitivity/` | Threshold sensitivity runs |
| `inventory_candidates.json` | The census inventory of artifacts |
| `metal_replication.json`, `referee_round2.json`, `heldout_49.json`, `sensitivity_sample.json` | Adjudication and robustness inputs |
| `muse_case_study.json`, `muse-glimmer-tracking/` | Day-zero case study of community conversions of a newly released model |

## Reproduce the paper's numbers

Stdlib Python only:

```
python3 analysis/analyze.py
```

This rereads the scored results and rewrites `analysis/findings.json`. The
committed copy was produced by exactly this command on this data.

## Smoke-test an artifact yourself

Requirements: Python 3.9+, [Ollama](https://ollama.com) serving locally
(the study pinned v0.32.6), and [EvalPlus](https://github.com/evalplus/evalplus)
for scoring.

```
python3 harness/audit.py --only qwen2.5-coder:3b-instruct-q3_K_M
python3 harness/score_smoke.py
```

`audit.py` pulls the artifact, runs the 15 suite tasks at temperature 0,
records the transcript and cheap output features, and removes the model.
`score_smoke.py` scores transcripts with EvalPlus and attaches verdicts.
A healthy configuration passes all 15 tasks; the confirmed-defective
artifacts pass none. A low score alone convicts nobody: before calling an
artifact defective, the study checks family baselines, both GPU backends,
and an independent conversion of the same model at the same quantization
level. The full adjudication rule is in the paper.

## Confirmed defects (as of the census)

| Artifact | Smoke result |
|---|---|
| `qwen2.5-coder:3b-instruct-q2_K` | 0/15 |
| `qwen2.5-coder:3b-instruct-q3_K_S` | 0/15 |
| `qwen2.5-coder:3b-instruct-q3_K_M` | 0/15 (1.3% on the full 542-task EvalPlus suite) |
| `qwen2.5-coder:3b-instruct-q3_K_L` | 0/15 |
| `phi3.5:3.8b-mini-instruct-q2_K` | 0/15 |

Independent conversions of the same models at the same quantization levels
pass most of the suite (8 to 14 of 15 for the Qwen batch, 6 of 15 for the
phi3.5 artifact), which is what makes these files defective rather than the
models weak. Upstream reports for the confirmed defects are tracked in
`disclosure/DISCLOSURES.md`.

## License

Code is released under the MIT License (see `LICENSE`). The audit dataset
(everything under `results*/` and the top-level JSON data files) is released
under CC BY 4.0.

## Citing

See `CITATION.cff`, or cite the paper above. If quantcheck catches a broken
artifact for you, an issue report here is always welcome.
