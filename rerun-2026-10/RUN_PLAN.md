# P2 run plan — written 2026-10-20, before any run

Everything below is fixed **before** results exist: the decision rule, the artifacts, the settings,
and the false-negative sample (`fn_sample_30.json`, drawn with seed 20261021). Report whatever comes
out. If the plan has to change mid-run, record the change and the reason here before looking at
the affected results.

Why these runs: the 2026-10-20 audit (`../../paper2_quant_audit_venue-IEEE-Big Data/V2_AUDIT_2026-10-20.md`)
found that the phi3.5 "plain referee" is the library's own tensors, and that the Qwen "plain"
referees are AWQ-calibrated. All three BigData reviewers questioned the validation of the screening
procedure.

---

## Pod configuration

| | Need | Why |
|---|---|---|
| GPU | **1 × RTX 4090, 24 GB** | Same card as the census, so the backend matches |
| NVIDIA driver | Supports CUDA 13 (the census pod reported driver 13.0) | Ollama 0.32.6 ships its own `cuda_v13` libraries; no CUDA toolkit needed |
| System RAM | **≥ 32 GB** | `convert_hf_to_gguf.py` loads the 3.8B phi3.5 checkpoint in memory |
| vCPU | ≥ 8 | Building llama.cpp and quantizing (CPU-only build is fine) |
| Disk (volume) | **≥ 100 GB** | Originals ~14 GB + F16 GGUFs ~14 GB + quants ~8 GB + one census artifact at a time (largest 8 GB; models are deleted after each run) |
| Network | Fast egress | ~14 GB from Hugging Face + ~125 GB of sequential Ollama pulls for the FN sample |
| OS image | Ubuntu 22.04 or 24.04, Python ≥ 3.10 | |
| Software | **Ollama 0.32.6** (pinned binary from the GitHub release, same as census); **EvalPlus 0.3.1**; llama.cpp at a recorded release tag; `huggingface_hub` | Same runtime and scorer as the published runs |
| Ollama env | `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MODELS=/workspace/omodels` | As in the census pod's `serve.log` |
| Copy to pod | `harness/` (from `control-run/harness`), `smoke_suite_v1.json`, `heldout_49.json`, `run-plan/fn_sample_30.json` | |

Generation options are unchanged from the census unless a run says otherwise:
`temperature 0.0, seed 42, num_predict 768, num_ctx 2048`, chat template copied verbatim from the
official sibling tag.

Mac (M2, 16 GB) is the backup for R1 only.

Estimated pod time: setup ~1 h, R1 ~2 h, R2 ~1.5–2 h, R3 ~3.5 h, R4 ~0.5 h → **~8–9 h**, mostly
unattended.

---

## Decision rule (pre-registered)

The paper's published rule, unchanged (main.tex, Method): *a suspect is confirmed defective only when
it scores at or under 2 of 15 while the referee reaches at least 5 of 15 and exceeds the suspect by at
least 4 tasks; when the referee fails comparably, the verdict is capability collapse.*

Added for this run:

1. **The deciding referee is our own plain conversion** (R1 below): original checkpoint → llama.cpp
   F16 GGUF → `llama-quantize` at the **same level**, no `--imatrix`, no AWQ. imatrix (bartowski) and
   AWQ (Qwen official GGUF) referees are reported alongside but do not decide.
2. If only a calibrated referee clears the bar and the plain one does not, the verdict is
   **capability collapse at that level** (calibration rescues it). It is not a defect.
3. **Referee independence** is checked on the tensor payload (hash of tensor data and tensor-info
   table), not the whole file. A referee whose tensor hash equals the suspect's is void.
4. Suspect and referee are scored **in the same session, same machine, same Ollama build**.

Possible outcomes, per artifact:

| Suspect | Plain self-quant referee | Verdict |
|---|---|---|
| ≤ 2/15 | ≥ 5/15 and ≥ 4 above suspect | **Defect** |
| ≤ 2/15 | < 5/15, or within 3 of suspect | **Capability collapse** |
| > 2/15 now | — | Not reproduced. Investigate before anything else |

The confirmed count is whatever this table gives: it can be 3, 4 or 5.

---

## R1 — self-quantized referees (decides the count)

Sources (record the HF commit SHA of each):
- `Qwen/Qwen2.5-Coder-3B-Instruct` (safetensors, not the AWQ or GGUF repos)
- `microsoft/Phi-3.5-mini-instruct`

Steps:
1. Build llama.cpp (CPU) at a recorded tag. `convert_hf_to_gguf.py --outtype f16` for each.
2. `llama-quantize` (no imatrix): Qwen → Q2_K, Q3_K_S, Q3_K_M, Q3_K_L; phi3.5 → Q2_K, plus Q3_K_S and
   Q3_K_M to show the shape of the cliff.
3. Record whole-file SHA-256 and tensor-payload hash for every file. Check against the library blobs
   (`14c4247b…`, `9bb5d28b…`, the q3_K_S/q3_K_L blobs, `54d47caa…`) and all earlier referees.
4. Create Ollama models with the official sibling's template; run the 15-task suite.

Run list, one session:

| Group | Artifacts |
|---|---|
| Library suspects | qwen2.5-coder:3b-instruct-q2_K, q3_K_S, q3_K_M, q3_K_L; phi3.5:3.8b-mini-instruct-q2_K |
| Healthy siblings | qwen2.5-coder:3b-instruct-q4_K_M; phi3.5:3.8b-mini-instruct-q4_K_M |
| **Plain self-quant referees** | Qwen Q2_K, Q3_K_S, Q3_K_M, Q3_K_L; phi3.5 Q2_K, Q3_K_S, Q3_K_M |
| Calibrated referees (report only) | bartowski Qwen Q2_K, Q3_K_S, Q3_K_M, Q3_K_L (exact levels); bartowski phi3.5 Q2_K; Qwen-official AWQ q2_k, q3_k_m |

About 23 smoke runs.

## R2 — generation-settings sensitivity (Reviewer 2)

Artifacts: the 5 library suspects, the 2 healthy siblings, and the plain referees at Qwen Q2_K / Q3_K_M
and phi3.5 Q2_K (10 artifacts).

Settings, one factor at a time around the baseline:

| Setting | Values |
|---|---|
| Baseline | ctx 2048, predict 768, greedy (temperature 0, seed 42) |
| Context | 4096; 8192 |
| Output limit | 2048 |
| Decoding | temperature 0.2 with seeds 1, 2, 3 |

7 settings × 10 artifacts = 70 smoke runs.

Reading (fixed now): a verdict is **robust** if the R1 rule gives the same answer under every
setting. Any setting that flips a verdict is reported, with its transcripts.

## R3 — false-negative audit extension (Reviewers 1 and 2)

Same protocol as v1: the **49 held-out tasks** in `heldout_49.json`, same options.

- Frame: 223 census official artifacts that passed stage one (≥ 9 of 15), excluding the 23
  calibration configs in the census and the 10 artifacts already audited in v1.
- Sample: **29** artifacts, 3 per family group with seed 20261021 (starcoder2 has only 2 in the
  frame). List in `fn_sample_30.json`.
- Trigger (fixed now): any sampled artifact solving **≤ 2 of 49** goes to full 164-task evaluation
  and R1-style referee adjudication.
- Report the miss rate over all **39** sampled artifacts (v1's 10 plus these 29) with a Wilson 95%
  interval. If none are missed, the upper bound is about 9%, against 27.8% now.

## R4 — task-type probe (Reviewer 1, optional, ~30 min)

For the 4 Qwen suspects, their healthy sibling and the plain referees: 15 MBPP+ tasks (fixed list,
first 15 by id) and 10 short non-code prompts. This shows whether the defects are specific to Python
code generation or general. Report descriptively; no verdicts change.

## A1 — suite-size and task-choice analysis (Reviewer 2, no GPU)

Run locally from existing data:
- Census: for k = 3…15, draw 1,000 random k-subsets of the 15 suite tasks; rescale the stage-one
  threshold (fewer than 60% of k); report how the flag set and the suspect set change (Jaccard with
  the full suite), and whether every confirmed defect is still caught.
- Calibration (P1's 24 configs with full HumanEval+ and MBPP+ per-task results): draw alternative
  15-task suites from the 39 always-solved tasks and from all 164; report the healthy-config pass
  distribution for each.

---

## After the runs

1. Lock the defect count from R1 and record it here with the date.
2. Only then edit the manuscript, the arXiv package, the repo, the HF dataset and the #18252 follow-up.
3. Raw results go to `p2-v2-work/rerun-2026-10/` (transcripts, scored JSONL, hashes, llama.cpp tag,
   HF commit SHAs, `ollama --version`, `nvidia-smi` output).

---

## Log

**2026-10-21, R1 (pod, RTX 4090, Ollama 0.32.6, llama.cpp v0.7.0 `620d222`).** Sources: Qwen
`488639f`, phi3.5 `2fe1924`. Every referee's tensor hash differs from the library artifact it referees.
Library files are byte-identical to the census blobs (`14c4247b…`, `9bb5d28b…`).

| Artifact | Library | Plain (ours) | imatrix | AWQ |
|---|---|---|---|---|
| qwen2.5-coder:3b q2_K | 0/15 | 0/15 | 15/15 | 14/15 |
| q3_K_S | 0/15 | 0/15 | 4/15 | — |
| q3_K_M | 0/15 | 0/15 | 10/15 | (see results) |
| q3_K_L | 0/15 | 0/15 | 9/15 | — |
| phi3.5 q2_K | 0/15 | 4/15 | 7/15 | — |
| q4_K_M siblings | Qwen 15/15, phi3.5 11/15 | | | |

**Control added after seeing R1** (recorded here because it was not in the plan): plain Qwen from the
same checkpoint and llama.cpp at Q6_K and Q4_K_M, to rule out a broken conversion pipeline. Both
scored **15/15**. F16 and Q8_0 could not be created (Ollama's validation copy ran out of local disk).
The control does not change the decision rule.

**Extension, written 2026-10-21 before these runs** (so the pod stays busy after R3):

- **R5, controlled calibration.** Same source checkpoints, same llama.cpp commit, same quantizer; the only
  change is an importance matrix we compute ourselves (`llama-imatrix`, 100 chunks of WikiText-2 train,
  CPU). Quantize Qwen 3B at Q2_K, Q3_K_S, Q3_K_M, Q3_K_L and phi3.5 at Q2_K, Q3_K_S, Q3_K_M; score on the
  15-task suite. Reading fixed now: calibration rescues a level when our imatrix quant scores ≥ 5/15 and
  ≥ 4 above our plain quant at that level. This separates calibration from every other difference
  between our files and bartowski's or Qwen's.
- **R6, full 164-task evaluation** of the rescue set and controls: our imatrix Qwen quants, bartowski
  Qwen Q2_K, Qwen-official AWQ q2_k and q3_k_m, our plain Qwen Q4_K_M, library q4_K_M. Descriptive.
- **R3b, second false-negative sample.** 27 more unflagged artifacts (seed 20261022, 3 per family group,
  excluding everything already sampled; starcoder2 has none left), same 49 held-out tasks and trigger.
  With R3 and v1 that makes 66 artifacts; if none is missed the Wilson upper bound is about 5.5%.
  List in `fn_sample_b.json`.

**P0-b result (2026-10-21, CPU, order-independent per-tensor comparison):** the library Qwen q2_K,
q3_K_S, q3_K_M and q3_K_L files contain **all 434 tensors byte-identical** to our plain quantizations of
the original checkpoint; only metadata differs (name, licence, base-model fields, a sampling default). The
earlier tensor-hash mismatch was tensor order. phi3.5 q2_K: 165 of 197 tensors identical; the 32 `attn_qkv`
tensors are Q2_K in the library and Q3_K in ours (a newer llama.cpp Q2_K mix). Q4_K_M: 30 tensors differ in
type only (mix change between versions). Output: `/workspace/p2rerun/p0b_tensor_compare.jsonl`.

**R2 result (2026-10-21):** every verdict is stable across all seven settings (baseline, ctx 4096, ctx 8192,
num_predict 2048, temperature 0.2 × seeds 1-3). The five library suspects and the plain Qwen Q2_K/Q3_K_M score
0/15 under every setting; siblings stay healthy (Qwen q4_K_M 15 throughout, phi3.5 q4_K_M 9-11). Plain phi3.5
Q2_K ranges 0-4 and never reaches the rule's 5/15, so the "not a defect" verdict for phi3.5 holds under every
setting. Scores in `pod-results/results-r2/scored.jsonl`.

**P0-f result (2026-10-21):** our phi3.5 Q2_K rebuilt from the original checkpoint with `--tensor-type
attn_qkv=q2_k` has **all 197 tensors byte-identical** to the library blob. With P0-b, every one of the five
library suspects is now shown to be a plain (uncalibrated) llama.cpp quantization of the original weights;
phi3.5's library-vs-ours gap (0 vs 4) is the older Q2_K tensor mix. The rebuild's score follows in P0 smoke.
Output: `/workspace/p2rerun/p0f_compare.jsonl`.

**R3 result (2026-10-21):** 28 of 29 sampled unflagged artifacts ran (one registry 503, granite-code:3b
q3_K_L, is re-run in the retry pass). Scores on the 49 held-out tasks range 10-34; **none at or below the
2/49 trigger**, so no missed defect in this sample.

**R3 + R3b final (2026-10-21):** all 29 + 27 = 56 sampled unflagged artifacts ran (the registry-503 entry
succeeded on retry: 14/49). Scores on the 49 held-out tasks range 8-41; none at or below the 2/49
trigger. With v1's ten: **0 missed in 66**, Wilson 95% upper bound ≈ 5.5% (was 27.8%).

**R5 result (2026-10-21), our own WikiText imatrix vs our own plain build, same source, same llama.cpp
commit, same quantizer, same type mix:**

| Level | Plain (ours) | Own imatrix | Rescue (≥ 5 and ≥ 4 above plain)? |
|---|---|---|---|
| Qwen Q2_K | 0 | **15** | yes |
| Qwen Q3_K_S | 0 | 2 | no |
| Qwen Q3_K_M | 0 | **9** | yes |
| Qwen Q3_K_L | 0 | **7** | yes |
| phi3.5 Q2_K | 4 (library mix: 0) | **9** | yes |
| phi3.5 Q3_K_S | 9 | 11 | not collapsed |
| phi3.5 Q3_K_M | 10 | 9 | not collapsed |

Reading: with nothing but calibration changed, calibration rescues Qwen Q2_K, Q3_K_M, Q3_K_L and phi3.5
Q2_K; Qwen Q3_K_S stays collapsed. The third-party pattern (bartowski, AWQ) is reproduced with our own
toolchain, so the rescue is calibration, not "someone else's build".

**P0 smoke result (2026-10-21):** phi3.5 Q2_K rebuilt with the library's tensor mix (tensors identical to
the library blob) scores **0/15**, as predicted. Code-calibrated imatrix (P0-d) gives the same verdicts as
WikiText at every level: Qwen Q2_K **15**, Q3_K_S 4 (not rescued), Q3_K_M **8**, Q3_K_L **8**; phi3.5 Q2_K
**8** (plain 4: exactly at the rescue bar), Q3_K_S 11, Q3_K_M 10. The calibration text does not change any
verdict.

**R6 result (2026-10-21), Qwen2.5-Coder-3B on all 164 HumanEval+ tasks:**

| Level | Library = our plain (census) | Own imatrix | bartowski imatrix | Qwen AWQ |
|---|---|---|---|---|
| Q2_K | 0/164 | **106/164** | **104/164** | **102/164** |
| Q3_K_S | 0/164 | 13/164 | (P0-c) | — |
| Q3_K_M | 0/164 | **76/164** | (P0-c) | **125/164** |
| Q3_K_L | 0/164 | **80/164** | (P0-c) | — |
| Q4_K_M | library 132/164, our plain 129/164 | | | |

Reading: at the same nominal level, calibration is the difference between 0% and 46-76% on the full
benchmark; at 4 bits the uncalibrated recipe is fine.

**P0-c result (2026-10-21), all 164 tasks:**

| Build | Qwen Q2_K | Q3_K_S | Q3_K_M | Q3_K_L | phi3.5 Q2_K | phi3.5 Q3_K_S | phi3.5 Q3_K_M |
|---|---|---|---|---|---|---|---|
| Library = plain, library mix | 0 | 0 | 0 | 0 | **0** (rebuild) | — | — |
| Plain, current mix | (= library) | | | | 21 | 35 | 61 |
| Own imatrix, WikiText | 106 | 13 | 76 | 80 | 37 | 46 | 76 |
| Own imatrix, code | **113** | 25 | **89** | **86** | — | — | — |
| bartowski imatrix | 104 | 30 | 81 | 77 | 34 | — | — |
| Qwen AWQ | 102 | — | 125 | — | — | — | — |
| Library q4_K_M | Qwen 132 | | | | phi3.5 74 | | |

Reading: our own calibrated builds match third-party ones level by level (Qwen Q3_K_M 76-89 vs bartowski
81; Q3_K_L 80-86 vs 77; phi3.5 Q2_K 37 vs 34). Qwen Q3_K_S stays weak under every calibration (13-30).

**P0-e result (2026-10-21, `llama-perplexity`, WikiText-2 test, 20 × 512 tokens, CPU):**

| Build | Qwen2.5-Coder-3B | phi3.5-mini |
|---|---|---|
| F16 | 11.55 | 6.91 |
| Library q4_K_M | 12.14 | 7.20 |
| Plain (ours) Q4_K_M / Q6_K / Q8_0 | 12.11 / 11.80 / 11.60 | — |
| Library q2_K (= plain, identical tensors) | **66,391** | **184.1** (library-mix rebuild: 184.1) |
| Library q3_K_S / q3_K_M / q3_K_L (= plain) | **920 / 333 / 373** | — |
| Plain current-mix Q2_K / Q3_K_S / Q3_K_M | — | 12.30 / 9.44 / 8.15 |
| Own imatrix, WikiText: Q2_K / Q3_K_S / Q3_K_M / Q3_K_L | **14.4** / 214 / 72.7 / 73.2 | 10.39 / 8.88 / 7.75 |
| Own imatrix, code: Q2_K / Q3_K_S / Q3_K_M / Q3_K_L | **14.9** / 217 / 70.8 / 72.4 | 10.52 / 8.82 / 7.70 |

Reading: the dead library builds are extreme perplexity outliers (29× to 5,700× F16), so a no-execution
perplexity check would flag all of them. Calibration (either text) rescues Qwen Q2_K almost fully but
Q3_K_S/M/L only partly. The type mixes of library and our imatrix builds are identical tensor-for-tensor
(token_embd is Q6_K and tied in every Qwen build), so the difference is calibration alone. The WikiText
imatrix has a home advantage on this test set; the code imatrix gives the same picture. Logs in `ppl/`.

**P0 jobs, written 2026-10-21 before running** (the author asked for the pod to stay busy overnight):
- **P0-f, phi3.5 library mix.** Rebuild phi3.5 Q2_K from the same F16 with `--tensor-type attn_qkv=q2_k`
  (the library's mix) and compare tensors with the library blob; then score it. Reading fixed now: if all
  197 tensors match and it scores ≤ 2/15, the library phi3.5 q2_K is a plain quantization with an older
  mix, and the 0 vs 4 gap is the mix, not the file.
- **P0-d, code calibration.** A second imatrix per model from Python source code (llama.cpp's own `.py`
  files, first 1.5 MB, hash recorded; no benchmark content), same levels, scored on the suite. Same rescue
  reading as R5.
- **P0-e, perplexity as a no-execution check.** `llama-perplexity` on WikiText-2 test, 20 chunks of 512, CPU,
  for F16, library, plain, imatrix (WikiText and code) builds of both models. Descriptive; answers whether a
  cheap non-execution signal separates the dead builds.
- **P0-c, full 164 tasks** for the R1 cells R6 does not cover: phi3.5 plain Q2_K/Q3_K_S/Q3_K_M, our WikiText
  imatrix phi3.5 ×3, the library-mix rebuild, library phi3.5 q4_K_M, bartowski phi3.5 Q2_K and Qwen
  Q3_K_S/Q3_K_M/Q3_K_L, and our code-imatrix Qwen ×4. Descriptive.

**G1-lite, written 2026-10-21 before running** (keeps the pod busy after P0; ~1 h; open-licence models only):
same procedure as R1/R5/P0-b for Qwen2.5-Coder-**0.5B** and **1.5B**-Instruct at q2_K, q3_K_S, q3_K_M, q3_K_L:
pull the library tags, rebuild plain and WikiText-imatrix quants from the original checkpoints with the
same llama.cpp commit, compare tensors library vs plain, and score library, plain and imatrix builds on the
15-task suite in one session. Descriptive questions fixed now: (1) are the library's low-bit tags at these
sizes also tensor-identical to a plain rebuild (one uncalibrated recipe across sizes)? (2) how large is the
calibration gap where the library tags work? No verdict rule; nothing here can change the defect count.

**G1-lite result (2026-10-21):** tensor comparison, library tag vs our plain rebuild: **1.5B: all 338 tensors
byte-identical at all four levels.** 0.5B: every tensor stored at the same type is byte-identical (0 byte
differences); 96-144 tensors differ in type only (older llama.cpp mix, as for phi3.5). Smoke /15 (library /
plain / own imatrix):

| Level | 0.5B | 1.5B |
|---|---|---|
| q2_K | 12 / 9 / 11 | 12 / 12 / 11 |
| q3_K_S | 12 / 11 / 11 | 14 / 14 / 13 |
| q3_K_M | 14 / 15 / 14 | 14 / 14 / 14 |
| q3_K_L | 13 / 11 / 12 | 14 / 14 / 13 |

Reading: the registry used one uncalibrated recipe across 0.5B, 1.5B and 3B. It works at 0.5B and 1.5B
(calibration changes little there) and collapses only at 3B, where calibration rescues three of four levels.

**Storage (decided 2026-10-21 by the author):** the referee GGUFs (~29 GB: `quants/` plain + controls,
`quants-imat/` our imatrix quants) stay on the RunPod network volume `<RUNPOD_VOLUME>` at
`/workspace/p2rerun/`. Do **not** delete that volume when the pod is terminated; decide later. Everything
else (results, logs, hashes, scripts, both `.imatrix` files) is synced to
`p2-v2-work/rerun-2026-10/pod-results/`.

**Verdict under the pre-registered rule:** the plain referee fails comparably for all five suspects
(Qwen 0 vs 0 at every level; phi3.5 0 vs 4, below the 5/15 bar), so all five are **capability
collapse at that level, rescued by calibration**. Confirmed defects: **0**. Not yet reviewed with the
author; R2 and R3 continue because both are needed under either framing.
