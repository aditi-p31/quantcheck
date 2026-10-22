# Provenance map

This file maps each provenance statement of the paper to the file and record
in this repository that supports it. Paths are relative to the repository
root; `runs.jsonl` records are selected by their `id` and `setting` fields.
A SHA-256 is written by its first 8 hex digits; the records hold all 64.

Kinds of evidence:

- **raw**: written by the run itself (run records, server and tool logs,
  transcripts);
- **derived**: computed from raw records by a script in this repository, or
  extracted from a log that is not released (the extraction script is
  included);
- **external**: a public source outside this repository;
- **not released**: the evidence exists but is not part of this release.

Ollama blob names are the SHA-256 of the file, so a blob digest and a file
SHA-256 identify the same bytes.

## Census frame and files

| Statement | Record | Kind |
|---|---|---|
| The inventory was fixed on 10 August 2026, before testing | `inventory_candidates.json`: `"generated": "2026-08-10"` (the `frozen` flag was never switched; see the README, Data notes) | raw |
| The census ran on 12 August 2026; each artifact's pull time is logged | `results/audit_results.jsonl`: `ts_start`, `ts_end`, `pull_s` per artifact | raw |
| Which file each census artifact ran on | `rerun-2026-10/serial/census_digests.json`, `artifacts[tag]`: `blob_sha256` for the 305 official tags (one load per run window, 305 distinct files), `file_sha256` for the 29 Hugging Face files (the blob each file was imported as), each with its `serve_log_line` | derived from the census `serve.log` (not released) by `rerun-2026-10/serial/census_digests.py` |
| HF files ran with the chat template of the matching official tag | `results/audit_results.jsonl`: `template_donor`; `rerun-2026-10/results*/runs.jsonl`: `donor` | raw |

## Runtimes and toolchain

| Statement | Record | Kind |
|---|---|---|
| Ollama 0.32.6 for all generation runs | Census pod: `rerun-2026-10/serial/census_digests.json` `server.ollama_version`. October pod: `rerun-2026-10/logs.tar.xz`, `logs/serve.log` line 10 (`Listening on ... (version 0.32.6)`), and `rerun-2026-10/env.txt` line 2. Closure pod (third RTX 4090 pod, 22 October 2026): `rerun-2026-10/results-v1cases/serve_v1cases.log.xz` line 10 (`Listening on ... (version 0.32.6)`) and `results-v1cases/env_v1cases.txt` line 3. Release archive: `rerun-2026-10/ollama_tarball.sha256` (`dec2fa50`); the closure pod installed the same archive (`results-v1cases/ollama_tarball_v1cases.sha256`, `dec2fa50`). Mac (Metal): `rerun-2026-10/miss_audit/certificates.json` `summary.backends.mac_serve6` | raw (October, closure); derived (census, Mac) |
| Ollama's bundled llama.cpp is `96278e3` | `census_digests.json` `server.llama_cpp_build` = `96278e39f`; `logs.tar.xz`, `logs/serve.log` line 38 (`build 1 (96278e39f)`); closure pod: `results-v1cases/serve_v1cases.log.xz` line 39 (same build) | derived; raw |
| Rebuilds used llama.cpp v0.7.0 (`620d222`) on CPU | `rerun-2026-10/env.txt` line 3 (tag v0.7.0, commit `620d2225cc436ab0b001e3200e590e3b286ef9ab`); `logs.tar.xz`, `logs/quantize.log` and `logs/p0f-quantize.log` print `620d222`; build steps in `rerun-2026-10/scripts/setup_pod.sh` | raw |
| NVIDIA RTX 4090 with CUDA for the census and the reruns | Census: `census_digests.json` `server` (RTX 4090, CUDA, driver 13.0). October: `logs/serve.log` line 14 (driver 13.2) and `env.txt` line 5. Closure pod: `results-v1cases/serve_v1cases.log.xz` line 14 (RTX 4090, CUDA, driver 13.2, PCI `0000:81:00.0`; the October pod's is `0000:02:00.0`) and `results-v1cases/env_v1cases.txt` line 2 | derived; raw |
| Apple M2 with Metal for the replication | `certificates.json` `summary.backends.mac_serve6` (Apple M2, Metal); runs in `results-mac/` and `results-metalrep/` | derived; raw |
| Greedy decoding, seed 42, context 2,048, at most 768 new tokens | `harness/audit.py` (request options); `options` of every record in `rerun-2026-10/results*/runs.jsonl` | raw |
| Outputs repeat byte for byte when the same task sequence is rerun on one setup (225 of 225 in October) | `certificates.json` `summary.cross_pod_determinism_same_digest`: 15 census tags rerun on the October pod on the unchanged file, with the same GPU model, Ollama release, options and task order as the census; 225 of 225 answers identical to the census transcripts | derived from `results/transcripts/` and `rerun-2026-10/results*/transcripts/` |
| Rerunning census tags in a different task order on another machine changed 2 and 3 of 15 screen answers versus the census, and one verdict (granite-code HumanEval/107) flipped | The closure reruns ran all 164 tasks in `rerun-2026-10/scripts/all164.json` order (HumanEval/0, /1, /10, ...) on the closure pod; the census ran the 15 suite tasks in `smoke_suite_v1.json` order. On those 15 tasks, `rerun-2026-10/results-v1cases/transcripts/v1fn-granite-code_3b-instruct-q3_K_M__full164.jsonl` differs from `results/transcripts/granite-code_3b-instruct-q3_K_M.jsonl` on HumanEval/107 and /152 (2 of 15), and `v1fn-mistral_7b-instruct-q3_K_S__full164.jsonl` from `results/transcripts/mistral_7b-instruct-q3_K_S.jsonl` on HumanEval/3, /28 and /152 (3 of 15). Verdicts: `per_task` in `rerun-2026-10/serial/census_smoke_serial.jsonl` vs `results-v1cases/scored_serial.jsonl`; only granite-code HumanEval/107 changes (pass in the census, fail in the closure; screen 14 vs 13 of 15), mistral stays at 10 of 15. The 49 held-out answers match the v1 audit transcripts (`results-sensitivity/transcripts/`) on 41 and 40 of 49 (`closure_v1cases.json` `note`) | raw (checked for this release) |

## Source checkpoints and rebuilt files

| Statement | Record | Kind |
|---|---|---|
| Checkpoints at pinned revisions | `rerun-2026-10/source_commits.jsonl`: Qwen2.5-Coder-3B-Instruct `488639f1`, 1.5B `2e1fd397`, 0.5B `ea3f2471`, Phi-3.5-mini-instruct `2fe19245` | raw |
| | `rerun-2026-10/scripts/quantize_refs.sh` and `g1lite.sh` looked up each repository's current revision at run time, downloaded that revision and logged it here; `pc.sh`, `imatrix_refs.sh` and `p0_cpu.sh` pass the logged revisions explicitly. To rebuild the same files with the first two, replace the lookup with the logged revision. | note |
| Hash of every rebuilt and downloaded file | `hash` field of `rerun-2026-10/results*/runs.jsonl`: `file_sha256`, `tensor_sha256` (tensor order dependent), `n_tensors`, key metadata, `imatrix_keys` | raw |
| The registry files carry no `quantize.imatrix` keys | `rerun-2026-10/results/runs.jsonl`, setting `base`: `hash.imatrix_keys` is `[]` for `lib-qwen3b-q2_K`, `-q3_K_S`, `-q3_K_M`, `-q3_K_L` and `lib-phi35-q2_K`; calibrated builds list four `quantize.imatrix.*` keys (`results-r5/`, `results-p0/`, `results-p0c/`, `results-g1/`) | raw |
| The plain rebuilds carry no imatrix keys | Same field, `plain-qwen3b-*` and `plain-phi35-*` in `rerun-2026-10/results/runs.jsonl` | raw |

## Tensor identity per tag

Comparisons are tensor by tensor (type, shape and bytes), independent of tensor
order and metadata, by `rerun-2026-10/scripts/compare_tensors.py`. Type ids
follow ggml: 10 = Q2_K, 11 = Q3_K, 2 = Q4_0, 20 = IQ4_NL.

| Statement | Record | Kind |
|---|---|---|
| The four Qwen2.5-Coder-3B tags (q2_K, q3_K_S, q3_K_M, q3_K_L) match our uncalibrated rebuild in all 434 tensors; only metadata differs | `rerun-2026-10/p0b_tensor_compare.jsonl`, `a` = `lib-q2_K` ... `lib-q3_K_L`: `identical_tensors` 434, `type_differs` 0, `same_type_bytes_differ` 0; `kv_diff` lists the metadata differences | raw |
| The phi3.5 q2_K tag matches our rebuild in all 197 tensors once its 32 `attn_qkv` tensors use Q2_K | `rerun-2026-10/p0f_compare.jsonl` (`lib-phi-q2_K` vs `libmix-phi-Q2_K`): 197 identical. Against our rebuild with the current mix, `p0b_tensor_compare.jsonl` (`lib-phi-q2_K` vs `plain-phi-Q2_K`): 165 identical, 32 `attn_qkv` tensors at type 10 vs 11, no other difference | raw |
| The registry's Qwen2.5-Coder-1.5B q2_K to q3_K_L tags match our uncalibrated rebuild in all 338 tensors | `rerun-2026-10/g1_tensor_compare.jsonl`, `lib-qwen1.5b-*`: `identical_tensors` 338 | raw |
| The 0.5B files fall back to 4-bit types (IQ4_NL in the library, Q4_0 in our rebuild) | `g1_tensor_compare.jsonl`, `lib-qwen0.5b-*`: `type_differs` 96 to 144 of 290 tensors, examples at type 20 vs 2. The count of weight matrices (169) is not a field of the record | raw |
| Library and rebuild differ in tensor mix at q4_K_M | `p0b_tensor_compare.jsonl`, `lib-q4_K_M`: 404 identical, 30 `type_differs`, 0 byte differences among same-type tensors | raw |
| Library and rebuild give byte-identical answers on all 15 tasks at every level; the q3_K_M answer in the paper's output table is one of them | `rerun-2026-10/results/transcripts/lib-qwen3b-<level>__base.jsonl` and `plain-qwen3b-<LEVEL>__base.jsonl`: all 15 solutions equal at each of the four levels (checked for this release) | raw |
| Qwen's AWQ GGUF files store a separate output head (435 tensors) and read `Instruct-AWQ` | `rerun-2026-10/local_referee_hashes.jsonl` (`qwen_official_q2k`, `qwen_official_q3km`): `n_tensors` 435, `general.finetune` `Instruct-AWQ`, no imatrix keys; same `file_sha256` (`cf586261`, `fc3937db`) in `rerun-2026-10/results-r6/runs.jsonl` (`awq-qwen3b-q2_k`, `awq-qwen3b-q3_k_m`) | raw |

## Re-downloads and registry stability

| Statement | Record | Kind |
|---|---|---|
| All four Qwen files and the phi3.5 file re-downloaded in October 2026 are byte-identical to the census copies | `rerun-2026-10/results/runs.jsonl`, setting `base`, `lib-qwen3b-q2_K`, `-q3_K_S`, `-q3_K_M`, `-q3_K_L` and `lib-phi35-q2_K`: `hash.file_sha256` and `blob` `14c4247b`, `81d167af`, `9bb5d28b`, `7a88dc11` and `54d47caa`, equal to the `blob_sha256` of the five tags in `census_digests.json`. Each file was pulled once and reused by the six R2 settings (`results-r2/runs.jsonl`, same `blob`); the October `logs/serve.log` in `rerun-2026-10/logs.tar.xz` loads each blob 7 times. Per-tag check: `rerun-2026-10/gate/facts_b.json` `persistence` (`FACTS_B.md` section 3) | raw (October); derived (census) |
| The registry served the failing tags unchanged from August to October 2026 | For the five rebuilt suspects, the October `blob` in `rerun-2026-10/results/runs.jsonl` equals the census digest in `census_digests.json`. Across all October runs of census tags (`results*/runs.jsonl`, `kind` `ollama`), only `gemma3:4b-it-q8_0` loaded a different file (`b3ec6779` in August, `b46dd6d6` in October; see its row in `rerun-2026-10/miss_audit/certificates.csv`). The llama3.2-1B tags were not pulled again in October | raw; derived |
| An outside reader reproduced the q3_K_M failure on a CPU machine with Ollama 0.33.3 | The reader's public report cited in the paper | external |

## Referees and storefront copies

The third-party files were downloaded from the repositories' `main` branch
(`rerun-2026-10/scripts/run_entries.py`), so the run records hold the file
hash but not a revision. The paper cites a revision for each repository; at
those revisions the Hugging Face LFS SHA-256 of each file equals the recorded
hash. That comparison was made against the Hugging Face API and is not stored
in this release; anyone can repeat it with
`https://huggingface.co/api/models/<repo>/tree/<revision>`.

| Statement | Record | Kind |
|---|---|---|
| The phi3.5 library file is byte-identical to the QuantFactory upload | Library: `file_sha256` `54d47caa` (`rerun-2026-10/results/runs.jsonl`, `lib-phi35-q2_K`; `census_digests.json`). QuantFactory: `rerun-2026-10/local_referee_hashes.jsonl`, `quantfactory_phi35_q2k`, same `file_sha256` | raw |
| ... and to the neopolita upload | Hugging Face LFS SHA-256 of `neopolita/phi-3.5-mini-instruct-gguf` `phi-3.5-mini-instruct_q2_k.gguf`, checked from registry and Hugging Face headers and posted on ollama/ollama#18252 on 2026-09-11 (logged in `disclosure/DISCLOSURES.md`). No file record in this release | external |
| ... and tensor-identical to the lm-kit upload | `local_referee_hashes.jsonl`, `lmkit_phi35_q2k`: `tensor_sha256` `7ace7e9d`, equal to the library's (`lib-phi35-q2_K` in `rerun-2026-10/results/runs.jsonl`) and QuantFactory's; its file hash (`91ff782a`) differs by one added metadata key (`extra_keys_vs_std`: `lm-kit.model_producer`) | raw |
| bartowski imatrix referees (Qwen Q2_K to Q3_K_L, phi3.5 Q2_K) | `hash` of `imat-qwen3b-Q2_K` (`rerun-2026-10/results-r6/runs.jsonl`) and `imat-qwen3b-Q3_K_S`, `-Q3_K_M`, `-Q3_K_L`, `imat-phi35-Q2_K` (`results-p0c/runs.jsonl`): file and tensor hashes and the `quantize.imatrix.*` keys. The census used the same files for Qwen Q2_K, Q3_K_M and phi3.5 Q2_K (`census_digests.json`, `file_sha256` `2e66080a`, `27ffec3e`, `7425cb5f`) | raw; derived |
| Qwen's own GGUF files (AWQ-derived) | See the tensor-identity table; `local_referee_hashes.jsonl` and `results-r6/runs.jsonl` | raw |
| unsloth's Llama-3.2-1B Q2_K and Q3_K_S files: their file hashes match the uploader's revision | `census_digests.json`, `artifacts["hf:unsloth/Llama-3.2-1B-Instruct-GGUF/..."]`: `file_sha256` `8b7091a9` (Q2_K) and `7fe2f725` (Q3_K_S), the files imported in the census. The comparison with the LFS SHA-256 at the cited revision is external, as above. Their importance-matrix metadata was read from the GGUF metadata dump in the census `serve.log`, which is not released; tensors were not compared | derived; external; not released |
| TheBloke deepseek-coder-6.7B Q3_K_M and Q4_K_M files | `census_digests.json`: `file_sha256` `6c841fde` and `92da6238` | derived |

## Calibration texts and importance matrices

| Statement | Record | Kind |
|---|---|---|
| WikiText-2 train is the imatrix text | `rerun-2026-10/calib_sha256.txt` (`wiki.train.raw`, `6707892f`); download URL in `rerun-2026-10/scripts/imatrix_refs.sh`. The text is not redistributed; the test split used for perplexity was not hashed | raw |
| The code text is 1.5 MB of Python source from the llama.cpp repository | `rerun-2026-10/calib_code_sha256.txt` (`code.txt`, `28a5df2c`); the exact recipe is in `rerun-2026-10/scripts/p0_cpu.sh` and the README | raw |
| 100 chunks of 512 tokens | `logs.tar.xz`, `logs/imatrix-*.log`: `computing over 100 chunks, n_ctx=512` | raw |
| The importance matrices themselves | `rerun-2026-10/quants-imat/`, `quants-imat-code/`, `quants-g1/` (GGUF imatrix files with `imatrix.chunk_count`, `imatrix.chunk_size` and `imatrix.datasets` keys) | raw |
| Perplexity on WikiText-2 test, 20 chunks of 512 tokens | `rerun-2026-10/ppl/*.log`: `calculating perplexity over 20 chunks, n_ctx=512` and the `Final estimate` line; parsed into `numbers_regroup.json` `ppl` | raw; derived |

## Scoring

| Statement | Record | Kind |
|---|---|---|
| EvalPlus 0.3.1, HumanEval+ plus tests | `rerun-2026-10/serial/serial_summary.json` `env` (EvalPlus 0.3.1, HumanEval+ v0.1.10 with its dataset hash); pod packages in `rerun-2026-10/pip_freeze.txt` | raw |
| Every failed task was re-evaluated serially, with a 3% sample of passes, none of which changed | Method: `rerun-2026-10/serial/serial_rescore.py`. One line per evaluation: `serial/instances.jsonl` (`kind` = `fail`, `sample_pass`, or `full` for sets that stored only counts; EvalPlus statuses, reasons, timings). Changed verdicts: `serial/flips.jsonl`. Per-set counts: `serial/serial_summary.json` and `serial/SERIAL_REPORT.md` | raw |
| HumanEval/15 passes for 275 of 305 official artifacts, one also gains HumanEval/23, no pass turns into a fail | `numbers_regroup.json`: `he15_pass_official`, `artifacts_changed_vs_original_census` (`tasks_gained`, `any_loss`) | derived |
| The slowest HumanEval/15 test uses at most 18% of its time limit | `serial/SERIAL_REPORT.md`, "Flips by task id" (maximum runtime over limit 0.18 for the census set); repeats with `first_ratio` in `serial/stability.jsonl` | raw |
| Per-task serial scores of every result set | `rerun-2026-10/serial/*_serial.jsonl` (the original scores are kept unchanged in `results*/` and `rerun-2026-10/results*/scored.jsonl`); the closure runs, scored only serially, in `rerun-2026-10/results-v1cases/scored_serial.jsonl` | raw |
| The screen was tuned on 24 Qwen2.5-Coder configurations | `serial/tuning_configs.json` (names). Their per-task results belong to a separate study and are withheld; the tuning values in `numbers_regroup.json` (`tuning_serial`) and `a1_regroup.json` (`calibration_94pct_check`) are inherited from the committed outputs | not released |

## Miss audit

| Statement | Record | Kind |
|---|---|---|
| The 56 October audit tags were drawn at random before the audit, in two rounds of up to three per family stratum | The two seeded manifests: `rerun-2026-10/fn_sample_30.json` (seed 20261021, frame 223, 29 tags) and `fn_sample_b.json` (seed 20261022, frame 194, 27 tags), each with its seed, frame size, per-family count and tag list; dated entries in `rerun-2026-10/RUN_PLAN.md`. `rerun-2026-10/miss_audit/bounds.py` regenerates both lists, in order, from the seeds (`bounds.json` `seeded_draws_reproduced`, `seeded_draw_procedure`) | raw; derived |
| The draw of the 10 first-version audit tags is unrecorded | `sensitivity_sample.json` shows which 10 tags were picked, not how: no seed, script, frame or allocation rule was recorded. A seed search over 48 frame variants and about 300,000 seeds does not recover the draw (`rerun-2026-10/miss_audit/v1_seed_search.py`, `v1_seed_search.log`). All 10 files are at most 3.9 GB while 110 of the 233 frame tags are larger, so the sample looks restricted to files of at most 3.9 GB (`bounds.json` `v1_randomization_diagnostic`, a post hoc diagnostic; `miss_audit/BOUNDS.md` section 1) | raw; derived |
| The 49 audit tasks were fixed before the audit and do not overlap the suite | `heldout_49.json`; `certificates.json` `summary.tasks` (no shared task id, 64 distinct tasks) | raw; derived |
| All 66 audited tags are certified as not non-functional: 50 on the 49-task audit alone, 14 by screen plus audit on the same file digest, GPU model and Ollama release, 2 by full 164-task reruns on the census file | `rerun-2026-10/miss_audit/certificates.json` `summary.closure.status_counts_after_closure`; per row, the `status` column (pre-rerun) and the `closure` column of `certificates.csv` and `.json` (added after the rerun) | derived |
| `granite-code:3b-instruct-q3_K_M` and `mistral:7b-instruct-q3_K_S`, whose v1 audit run recorded no backend or digest, solve 65 and 44 of 164 on the census files (CUDA), scored serially | File: `blob` of `rerun-2026-10/results-v1cases/runs.jsonl` (`sha256-9c66e1aa`, `sha256-067ecc27`), equal to `rerun-2026-10/serial/census_digests.json` `artifacts[tag].blob_sha256`; the loads are lines 36 and 24790 of `results-v1cases/serve_v1cases.log.xz`. Pod: `results-v1cases/env_v1cases.txt` (RTX 4090, Ollama 0.32.6, 2026-10-22) and the same log. Scores: `results-v1cases/scored_serial.jsonl` (`n_pass` 65 and 44, `n` 164; `rerun-2026-10/scripts/score_v1cases_serial.py`, one EvalPlus worker). Summary: `rerun-2026-10/miss_audit/closure_v1cases.json`. Run script: `rerun-2026-10/scripts/v1cases.sh` | raw; derived |
| None of the 66 scores 2 of 49 or less; per-artifact evidence | `rerun-2026-10/miss_audit/certificates.csv` and `.json` (see the README, Miss-audit certificates); serial scores in `serial/rerun_r3_serial.jsonl`, `rerun_r3b_serial.jsonl`, `sensitivity_serial.jsonl` | derived |
| The audit frame holds 233 tags | `certificates.json` `summary.frame.frame_original_unflagged_non_tuning`; `numbers_regroup.json` `miss_audit_frame`; rebuilt with its ten strata in `bounds.json` `frame`, `strata` | derived |
| For the 223 tags outside the first-version sample, the 56 seeded draws give an exact stratified 95% bound of 22 non-functional census files (9.9%), counting the re-published `gemma3:4b-it-q8_0` August file as failed; tighter bounds need further assumptions | `rerun-2026-10/miss_audit/bounds.csv` and `bounds.json`, row 4; all rows (1 to 5 and 4b, 15 to 30 tags, each with its assumptions) in the table of `miss_audit/BOUNDS.md` section 4. Script `bounds.py` (exact test inversion over the strata); rows 1 to 4 repeated in exact fractions by `bounds_check.py` | derived |

## Output statistics and the proposed gate

| Statement | Record | Kind |
|---|---|---|
| The repetition statistic is a 6-gram repetition score: six times the count of the most frequent word 6-gram over the word count; it can exceed 1 | `harness/audit.py` lines 40 to 51 (`degeneration_features`, field `rep6_share`), averaged over the 15 generations at line 117 (`rep6_share_mean`). Values above 1 (up to 5.348 per generation, 2.049 per artifact): `rerun-2026-10/gate/facts_b.json` `rep6` | raw (code); derived |
| Truncation at or above 0.2 flags 10 non-suspect tags, five of which solve at most 16 of 164; either statistic at 0.3 or above flags 6, four of them deepseek-coder-1.3B tags solving 2 to 16 of 164 | `facts_b.json` `rq3` (`extra_rows`, `status_counts`), with full-run scores from `rerun-2026-10/serial/census_full164_serial.jsonl`; `gate/FACTS_B.md` section 1 | derived |
| On the census, the proposed gate would publish 8 of the 16 flagged non-suspect tags that have a full 164-task run and withhold 8 (seven deepseek-coder-1.3B tags and `gemma3:270m-it-q8_0`); 16 more have no full run | `facts_b.json` `gate.routing_rule_on_census` (rule text in `gate.routing_rule_text`); `gate/FACTS_B.md` section 2 | derived |
| The census full 164-task runs were chosen by a fixed rule, not at random | `harness/fullrun.py` lines 59 to 72: every official tag at most 2 of 15 (original scorer) plus the lowest-scoring tag at 3 to 8 of 15 per model and size key; 27 runs in `results/fullrun_scores.jsonl`, serial scores in `census_full164_serial.jsonl` | raw |

## Not in this release

- The quantized GGUF files (rebuilds and downloads) and the source
  checkpoints: identified by their hashes and revisions above.
- The census Ollama `serve.log`: its per-artifact digests and server header
  are in `rerun-2026-10/serial/census_digests.json`, and its per-load records
  for the deepseek-coder-1.3B diagnosis in `rerun-2026-10/ds13/servelog_loads.json`.
- The Mac server logs behind the Metal-side digests and server version in
  `certificates.json`.
- The calibration texts (hashes above).
- The per-task results of the 24 screen-tuning configurations (a summary of
  their full 164-task runs, counts and range, is in
  `rerun-2026-10/gate/facts_b.json`, marked `from_committed_file`).
