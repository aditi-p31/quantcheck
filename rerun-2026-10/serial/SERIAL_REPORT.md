# Serial re-scoring of every reported transcript set

Generated 2026-10-21 14:57 PDT by `serial_rescore.py report`.

Every score in the `*_serial.jsonl` files comes from evaluating generations one at a time (no worker pool, no other evaluation running), with EvalPlus' default time limits. Existing per-task verdicts were taken as they were; every instance that failed in any existing scoring was re-evaluated serially, and a seeded 3% sample of passes per set (random.Random(20261021) over the sorted pass instances, ceil(3%)) was re-evaluated to check that no pass turns into a failure. Sets whose scorer stored only counts were re-evaluated in full. Sanitizing is the original scorers' own: each transcript is padded to 164 tasks with the scorer's placeholder and passed through the `evalplus.sanitize` CLI; paper-1 tuning configurations are re-evaluated from the exact sanitized solutions stored in their eval_results. Each instance is evaluated with `evalplus.evaluate.check_correctness`, the function `evalplus.evaluate` submits to its pool, with the same arguments.

## Environment

- EvalPlus 0.3.1; HumanEval+ v0.1.10 (md5 fe585eb4df8c88d844eeb463ea4d0302); MBPP+ v0.2.0 (md5 ee43ecabebf20deef4bb776a405ac5b1)
- Ground-truth cache (EvalPlus default location, reused, file mtime): {'fe585eb4df8c88d844eeb463ea4d0302.pkl': '2026-08-08 09:50', 'ee43ecabebf20deef4bb776a405ac5b1.pkl': '2026-08-10 01:02'}
- Python 3.9.6 on macOS-26.5.1-arm64-arm-64bit, 8 CPUs, multiprocessing start method `spawn`; packages {'tree_sitter': '0.23.2', 'tree_sitter_python': '0.23.6', 'numpy': '2.0.2', 'psutil': '7.2.2'}
- Time limits: per test max(DEFAULT_MIN_TIME_LIMIT = 1.0 s, DEFAULT_GT_TIME_LIMIT_FACTOR = 4.0 x ground-truth time); per check min(60, sum of limits) + 1 s (EvalPlus defaults, unchanged)
- 1-minute load average at set boundaries: 1.80 to 3.17 on 8 CPUs (the serial evaluation itself accounts for about 1)
- Total wall time of the serial runs: 3.59 h

## Per set

| Set | Universe | Runs | Re-evaluated: failures / 3% pass sample (of passes) / full | Passes old -> serial | fail->pass | pass->fail | Wall time |
|---|---|---|---|---|---|---|---|
| census_smoke | smoke15 | 334 | 1294 / 112 (of 3716) / 0 | 3859 -> 4018 | 159 | 0 | 37.7 min |
| census_full164 | full164 | 27 | 0 / 0 (of 0) / 4428 | 510 -> 520 (count level: 10 runs changed) | 0 | 0 | 46.8 min |
| rerun_results | smoke15 | 23 | 192 / 5 (of 153) / 0 | 153 -> 153 | 0 | 0 | 2.4 min |
| rerun_r2 | smoke15 | 60 | 730 / 6 (of 170) / 0 | 170 -> 170 | 0 | 0 | 10.4 min |
| rerun_r3 | heldout49 | 29 | 797 / 19 (of 624) / 0 | 624 -> 625 | 1 | 0 | 8.2 min |
| rerun_r3b | heldout49 | 27 | 727 / 18 (of 596) / 0 | 596 -> 596 | 0 | 0 | 7.4 min |
| rerun_r5 | smoke15 | 7 | 43 / 2 (of 62) / 0 | 62 -> 62 | 0 | 0 | 0.6 min |
| rerun_r6 | full164 | 9 | 609 / 27 (of 867) / 0 | 867 -> 867 | 0 | 0 | 6.5 min |
| rerun_p0 | smoke15 | 8 | 56 / 2 (of 64) / 0 | 64 -> 64 | 0 | 0 | 0.7 min |
| rerun_p0c | full164 | 16 | 1739 / 27 (of 885) / 0 | 885 -> 885 | 0 | 0 | 17.1 min |
| rerun_g1 | smoke15 | 24 | 56 / 10 (of 304) / 0 | 304 -> 327 | 23 | 0 | 2.9 min |
| mac | smoke15 | 3 | 45 / 0 (of 0) / 0 | 0 -> 0 | 0 | 0 | 0.6 min |
| metalrep | smoke15 | 4 | 32 / 1 (of 28) / 0 | 28 -> 28 | 0 | 0 | 0.4 min |
| native | full164 | 2 | 0 / 0 (of 0) / 328 | 38 -> 38 (count level: 0 runs changed) | 0 | 0 | 3.5 min |
| sensitivity | heldout49 | 10 | 0 / 0 (of 0) / 490 | 206 -> 206 (count level: 0 runs changed) | 0 | 0 | 4.9 min |
| tuning_p1_humaneval | full164 | 24 | 1380 / 77 (of 2556) / 0 | 2556 -> 2556 | 0 | 0 | 14.1 min |
| tuning_p1_mbpp | mbpp378 | 24 | 4182 / 147 (of 4890) / 0 | 4890 -> 4899 | 9 | 0 | 51.5 min |

Old sources: census_full164: results/fullrun_scores.jsonl (count only; per-task not stored); census_smoke: census_rescore.jsonl (pod, 6-worker pool); mac: results-mac/audit_scored.jsonl (Mac, score_smoke.py); metalrep: results-metalrep/audit_scored.jsonl (Mac, score_smoke.py); native: analysis/experiments.json (Mac, score_experiments.py; counts only); rerun_g1: results-g1/scored.jsonl (pod, score_runs.py pool); rerun_p0: results-p0/scored.jsonl (pod, score_runs.py pool); rerun_p0c: results-p0c/scored.jsonl (pod, score_runs.py pool); rerun_r2: results-r2/scored.jsonl (pod, score_runs.py pool); rerun_r3: results-r3/scored.jsonl (pod, score_runs.py pool); rerun_r3b: results-r3b/scored.jsonl (pod, score_runs.py pool); rerun_r5: results-r5/scored.jsonl (pod, score_runs.py pool); rerun_r6: results-r6/scored.jsonl (pod, score_runs.py pool); rerun_results: results/scored.jsonl (pod, score_runs.py pool); sensitivity: analysis/experiments.json (Mac, score_experiments.py; counts only); tuning_p1_humaneval: paper-1 humaneval eval_results (Mac, evalplus.evaluate default pool); tuning_p1_mbpp: paper-1 mbpp eval_results (Mac, evalplus.evaluate default pool)

## Flips by task id

All sets: HumanEval/15 fail->pass: 182, Mbpp/392 fail->pass: 7, HumanEval/130 fail->pass: 1, Mbpp/599 fail->pass: 1, Mbpp/160 fail->pass: 1

| Set | Task | fail->pass | pass->fail | serial max runtime / per-test limit (min / median / max) | serial repeats all pass |
|---|---|---|---|---|---|
| census_smoke | HumanEval/15 | 159 | 0 | 0.09 / 0.11 / 0.18 | 159 of 159 (318 repeats) |
| rerun_g1 | HumanEval/15 | 23 | 0 | 0.09 / 0.11 / 0.15 | 23 of 23 (46 repeats) |
| rerun_r3 | HumanEval/130 | 1 | 0 | 0.34 / 0.34 / 0.34 | 1 of 1 (5 repeats) |
| tuning_p1_mbpp | Mbpp/160 | 1 | 0 | 0.91 / 0.91 / 0.91 | 1 of 1 (5 repeats) |
| tuning_p1_mbpp | Mbpp/392 | 7 | 0 | 0.68 / 0.69 / 0.79 | 7 of 7 (35 repeats) |
| tuning_p1_mbpp | Mbpp/599 | 1 | 0 | 0.70 / 0.70 / 0.70 | 1 of 1 (5 repeats) |

- **census_full164** stored only counts, so flips are identified at count level: llama3.2:1b-instruct-q3_K_M 41 -> 42 (HumanEval/15 serial: pass); llama3.2:3b-instruct-q2_K 29 -> 30 (HumanEval/15 serial: pass); phi3.5:3.8b-mini-instruct-q3_K_S 41 -> 42 (HumanEval/15 serial: pass); deepseek-coder:1.3b-instruct-q3_K_S 6 -> 7 (HumanEval/15 serial: pass); deepseek-coder-v2:16b-lite-instruct-q2_K 24 -> 25 (HumanEval/15 serial: pass); mistral:7b-instruct-v0.2-q3_K_L 43 -> 44 (HumanEval/15 serial: pass); starcoder2:15b-instruct-v0.1-q2_K 64 -> 65 (HumanEval/15 serial: pass); granite-code:20b-instruct-q2_K 45 -> 46 (HumanEval/15 serial: pass); granite3.1-dense:2b-instruct-q2_K 16 -> 17 (HumanEval/15 serial: pass); yi-coder:1.5b-chat-q2_K 47 -> 48 (HumanEval/15 serial: pass)

## Runs whose reported pass count changes

- **census_smoke** (159 of 334 runs): qwen2.5-coder:0.5b-instruct-q3_K_S 12->13; qwen2.5-coder:0.5b-instruct-q3_K_M 14->15; qwen2.5-coder:0.5b-instruct-q2_K 12->13; qwen2.5-coder:0.5b-instruct-q3_K_L 13->14; qwen2.5-coder:0.5b-instruct-q4_K_M 13->14; qwen2.5-coder:0.5b-instruct-q4_K_S 13->14; qwen2.5-coder:0.5b-instruct-q5_K_M 14->15; qwen2.5-coder:0.5b-instruct-q5_K_S 14->15; qwen2.5-coder:0.5b-instruct-q8_0 14->15; qwen2.5-coder:0.5b-instruct-q6_K 13->14; qwen2.5-coder:0.5b-instruct-fp16 14->15; qwen2.5-coder:1.5b-instruct-q3_K_L 14->15; qwen2.5-coder:1.5b-instruct-q3_K_M 14->15; qwen2.5-coder:1.5b-instruct-q4_K_S 14->15; qwen2.5-coder:3b-instruct-q4_K_S 14->15; qwen2.5-coder:3b-instruct-q5_K_M 14->15; qwen2.5-coder:3b-instruct-q6_K 14->15; qwen2.5-coder:3b-instruct-q8_0 14->15; qwen2.5-coder:3b-instruct-fp16 14->15; qwen2.5-coder:7b-instruct-q2_K 13->14; qwen2.5-coder:7b-instruct-q3_K_M 14->15; qwen2.5-coder:7b-instruct-q3_K_L 14->15; qwen2.5-coder:7b-instruct-q4_K_M 14->15; qwen2.5-coder:7b-instruct-q5_K_M 14->15; qwen2.5-coder:7b-instruct-q6_K 14->15; qwen2.5-coder:14b-instruct-q2_K 14->15; qwen2.5-coder:14b-instruct-q3_K_S 14->15; qwen2.5-coder:14b-instruct-q3_K_M 14->15; llama3.2:1b-instruct-q3_K_M 7->8; llama3.2:1b-instruct-q3_K_L 7->8; llama3.2:1b-instruct-q4_0 7->8; llama3.2:1b-instruct-q4_K_S 7->8; llama3.2:1b-instruct-q4_K_M 8->9; llama3.2:1b-instruct-q8_0 10->11; llama3.2:3b-instruct-q2_K 6->7; llama3.2:3b-instruct-q3_K_L 13->14; llama3.2:3b-instruct-q3_K_M 14->15; llama3.2:3b-instruct-q3_K_S 11->12; llama3.2:3b-instruct-q5_K_M 14->15; llama3.2:3b-instruct-q8_0 14->15; llama3.1:8b-instruct-q3_K_M 12->13; llama3.1:8b-instruct-q3_K_L 14->15; llama3.1:8b-instruct-q4_0 12->13; llama3.1:8b-instruct-q4_K_M 14->15; llama3.1:8b-instruct-q5_K_M 14->15; llama3.1:8b-instruct-q6_K 14->15; llama3.1:8b-instruct-q5_K_S 14->15; gemma2:2b-instruct-q3_K_M 10->11; gemma2:2b-instruct-q3_K_L 11->12; gemma2:2b-instruct-q4_K_M 10->11; gemma2:2b-instruct-q5_K_M 9->10; gemma2:2b-instruct-q6_K 11->12; gemma2:2b-instruct-q8_0 10->11; gemma2:9b-instruct-q3_K_M 12->13; gemma2:9b-instruct-q3_K_L 12->13; gemma2:9b-instruct-q4_0 12->13; gemma2:9b-instruct-q4_K_S 12->13; gemma2:9b-instruct-q4_K_M 13->14; phi3.5:3.8b-mini-instruct-q3_K_S 8->9; phi3.5:3.8b-mini-instruct-q3_K_M 13->14; phi3.5:3.8b-mini-instruct-q4_0 12->13; phi3.5:3.8b-mini-instruct-q4_K_S 10->11; phi3.5:3.8b-mini-instruct-q5_K_M 11->12; phi3.5:3.8b-mini-instruct-q8_0 13->14; deepseek-coder:6.7b-instruct-q3_K_S 12->13; deepseek-coder:6.7b-instruct-q4_K_S 14->15; deepseek-coder:6.7b-instruct-q4_0 12->13; deepseek-coder:6.7b-instruct-q5_K_S 14->15; deepseek-coder:6.7b-instruct-q5_K_M 13->14; deepseek-coder:6.7b-instruct-q8_0 13->14; deepseek-coder-v2:16b-lite-instruct-q3_K_S 14->15; mistral:7b-instruct-q4_K_S 10->11; mistral:7b-instruct-q4_0 8->9; mistral:7b-instruct-q4_K_M 10->11; mistral:7b-instruct-q5_K_M 9->10; mistral:7b-instruct-q8_0 10->11; mistral:7b-instruct-v0.2-q3_K_M 9->10; mistral:7b-instruct-v0.2-q3_K_L 6->7; mistral:7b-instruct-v0.2-q5_K_M 6->7; mistral:7b-instruct-v0.3-q3_K_S 11->12; mistral:7b-instruct-v0.3-q4_K_S 11->12; mistral:7b-instruct-v0.3-q5_K_S 9->10; mistral:7b-instruct-v0.3-q4_K_M 10->11; codellama:7b-instruct-q2_K 12->13; codellama:7b-instruct-q3_K_S 11->12; codellama:7b-instruct-q3_K_L 12->13; codellama:7b-instruct-q4_K_S 11->12; codellama:7b-instruct-q8_0 12->13; codellama:13b-instruct-q3_K_L 14->15; codellama:13b-instruct-q4_0 11->12; starcoder2:15b-instruct-v0.1-q3_K_S 10->11; granite-code:3b-instruct-q6_K 13->14; granite-code:3b-instruct-q8_0 12->13; granite-code:3b-instruct-128k-q3_K_M 13->14; granite-code:3b-instruct-128k-q3_K_L 13->14; granite-code:3b-instruct-128k-q4_0 14->15; granite-code:3b-instruct-128k-q4_K_M 13->14; granite-code:3b-instruct-128k-q5_K_M 14->15; granite-code:8b-instruct-q3_K_M 12->13; granite-code:8b-instruct-q4_0 13->14; granite-code:8b-instruct-128k-q4_0 13->14; granite-code:8b-instruct-q4_K_S 14->15; granite-code:8b-instruct-q4_K_M 13->14; granite-code:8b-instruct-q5_K_S 13->14; granite-code:20b-instruct-8k-q2_K 13->14; granite3.1-dense:2b-instruct-q2_K 4->5; granite3.1-dense:2b-instruct-q3_K_M 9->10; granite3.1-dense:2b-instruct-q3_K_L 9->10; granite3.1-dense:2b-instruct-q4_K_S 12->13; granite3.1-dense:2b-instruct-q5_K_S 13->14; granite3.1-dense:8b-instruct-q2_K 9->10; granite3.1-dense:8b-instruct-q3_K_M 14->15; granite3.1-dense:8b-instruct-q4_0 14->15; granite3.1-dense:8b-instruct-q3_K_L 13->14; granite3.1-dense:8b-instruct-q5_K_S 14->15; granite3.1-dense:8b-instruct-q5_K_M 14->15; granite3.1-dense:8b-instruct-q6_K 13->14; yi-coder:1.5b-chat-q2_K 8->9; yi-coder:1.5b-chat-q3_K_L 13->14; yi-coder:1.5b-chat-q3_K_M 11->12; yi-coder:1.5b-chat-q3_K_S 10->11; yi-coder:1.5b-chat-q4_0 12->13; yi-coder:1.5b-chat-q5_K_M 13->14; yi-coder:1.5b-chat-q6_K 14->15; yi-coder:1.5b-chat-q8_0 14->15; yi-coder:9b-chat-q3_K_S 12->13; yi-coder:9b-chat-q3_K_M 12->13; yi-coder:9b-chat-q4_K_S 13->14; yi-coder:9b-chat-q4_K_M 13->14; yi-coder:9b-chat-q5_K_S 13->14; yi-coder:9b-chat-q6_K 13->14; codegemma:7b-instruct-q3_K_L 11->12; codegemma:7b-instruct-q4_0 13->14; codegemma:7b-instruct-q4_K_S 12->13; codegemma:7b-instruct-q5_K_S 12->13; codegemma:7b-instruct-q6_K 14->15; codegemma:7b-instruct-v1.1-q3_K_M 13->14; codegemma:7b-instruct-v1.1-q4_0 14->15; codegemma:7b-instruct-v1.1-q5_K_S 13->14; codegemma:7b-instruct-v1.1-q6_K 13->14; codegemma:7b-instruct-v1.1-q5_K_M 13->14; hf:bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf 14->15; hf:bartowski/Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf 14->15; hf:lmstudio-community/Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf 13->14; hf:bartowski/Phi-3.5-mini-instruct-GGUF/Phi-3.5-mini-instruct-Q4_K_M.gguf 11->12; hf:lmstudio-community/Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q3_K_L.gguf 14->15; hf:bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-Q4_K_M.gguf 14->15; hf:bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-Q3_K_M.gguf 14->15; hf:bartowski/gemma-2-9b-it-GGUF/gemma-2-9b-it-Q4_K_M.gguf 13->14; hf:bartowski/gemma-2-9b-it-GGUF/gemma-2-9b-it-Q3_K_M.gguf 13->14; hf:bartowski/Qwen2.5-14B-Instruct-GGUF/Qwen2.5-14B-Instruct-Q3_K_M.gguf 14->15; hf:bartowski/Qwen2.5-14B-Instruct-GGUF/Qwen2.5-14B-Instruct-Q2_K.gguf 13->14; hf:lmstudio-community/Qwen2.5-Coder-14B-Instruct-GGUF/Qwen2.5-Coder-14B-Instruct-Q3_K_L.gguf 14->15; hf:bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf 14->15; hf:bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF/DeepSeek-Coder-V2-Lite-Instruct-Q2_K.gguf 12->13; hf:bartowski/microsoft_Phi-4-mini-instruct-GGUF/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf 11->12; hf:bartowski/microsoft_Phi-4-mini-instruct-GGUF/microsoft_Phi-4-mini-instruct-Q3_K_M.gguf 11->12; hf:bartowski/Llama-3.2-1B-Instruct-GGUF/Llama-3.2-1B-Instruct-Q3_K_L.gguf 8->9; hf:bartowski/Phi-3.5-mini-instruct-GGUF/Phi-3.5-mini-instruct-Q2_K.gguf 6->7
- **census_full164** (10 of 27 runs): llama3.2:1b-instruct-q3_K_M 41->42; llama3.2:3b-instruct-q2_K 29->30; phi3.5:3.8b-mini-instruct-q3_K_S 41->42; deepseek-coder:1.3b-instruct-q3_K_S 6->7; deepseek-coder-v2:16b-lite-instruct-q2_K 24->25; mistral:7b-instruct-v0.2-q3_K_L 43->44; starcoder2:15b-instruct-v0.1-q2_K 64->65; granite-code:20b-instruct-q2_K 45->46; granite3.1-dense:2b-instruct-q2_K 16->17; yi-coder:1.5b-chat-q2_K 47->48
- **rerun_r3** (1 of 29 runs): fn-deepseek-coder_6.7b-instruct-q4_0|heldout49 29->30
- **rerun_g1** (23 of 24 runs): g1plain-qwen0.5b-q2_K|base 9->10; g1imat-qwen0.5b-q2_K|base 11->12; g1imat-qwen0.5b-q3_K_S|base 11->12; g1lib-qwen0.5b-q2_K|base 12->13; g1plain-qwen0.5b-q3_K_S|base 11->12; g1lib-qwen0.5b-q3_K_S|base 12->13; g1imat-qwen0.5b-q3_K_M|base 14->15; g1plain-qwen0.5b-q3_K_L|base 11->12; g1imat-qwen0.5b-q3_K_L|base 12->13; g1lib-qwen0.5b-q3_K_M|base 14->15; g1lib-qwen0.5b-q3_K_L|base 13->14; g1lib-qwen1.5b-q3_K_S|base 14->15; g1plain-qwen1.5b-q3_K_S|base 14->15; g1plain-qwen1.5b-q2_K|base 12->13; g1imat-qwen1.5b-q3_K_S|base 13->14; g1lib-qwen1.5b-q2_K|base 12->13; g1imat-qwen1.5b-q2_K|base 11->12; g1plain-qwen1.5b-q3_K_L|base 14->15; g1lib-qwen1.5b-q3_K_M|base 14->15; g1lib-qwen1.5b-q3_K_L|base 14->15; g1imat-qwen1.5b-q3_K_L|base 13->14; g1plain-qwen1.5b-q3_K_M|base 14->15; g1imat-qwen1.5b-q3_K_M|base 14->15
- **tuning_p1_mbpp** (8 of 24 runs): qwen2.5-coder_0.5b-instruct-q5_K_M 153->154; qwen2.5-coder_1.5b-instruct-fp16 212->213; qwen2.5-coder_1.5b-instruct-q3_K_M 203->205; qwen2.5-coder_1.5b-instruct-q8_0 210->211; qwen2.5-coder_3b-instruct-fp16 229->230; qwen2.5-coder_3b-instruct-q4_K_M 231->232; qwen2.5-coder_3b-instruct-q6_K 230->231; qwen2.5-coder_3b-instruct-q8_0 231->232
- native 15-task subset (old / serial): deepseek-coder-6.7b-instruct.Q3_K_M.native 6 / 6; deepseek-coder-6.7b-instruct.Q4_K_M.native 4 / 4

## Census consequences (rules of paper-v3/analysis/numbers_v3.py, analyze.py unchanged)

| Scoring | Stage-one flags (<9 of 15) | Classes | Suspects | HF community >= 9 |
|---|---|---|---|---|
| original (audit_scored) | 50 | {'COLLAPSED': 6, 'DEGRADED': 3, 'HEALTHY': 271, 'NO_BASELINE': 18, 'SUSPECT': 7} | 7: llama3.2:1b-instruct-q2_K, llama3.2:1b-instruct-q3_K_S, phi3.5:3.8b-mini-instruct-q2_K, qwen2.5-coder:3b-instruct-q2_K, qwen2.5-coder:3b-instruct-q3_K_L, qwen2.5-coder:3b-instruct-q3_K_M, qwen2.5-coder:3b-instruct-q3_K_S | 20 of 22 |
| pod rescore (census_rescore) | 43 | {'COLLAPSED': 6, 'DEGRADED': 3, 'HEALTHY': 271, 'NO_BASELINE': 18, 'SUSPECT': 7} | 7: llama3.2:1b-instruct-q2_K, llama3.2:1b-instruct-q3_K_S, phi3.5:3.8b-mini-instruct-q2_K, qwen2.5-coder:3b-instruct-q2_K, qwen2.5-coder:3b-instruct-q3_K_L, qwen2.5-coder:3b-instruct-q3_K_M, qwen2.5-coder:3b-instruct-q3_K_S | 20 of 22 |
| serial | 39 | {'COLLAPSED': 6, 'DEGRADED': 3, 'HEALTHY': 271, 'NO_BASELINE': 18, 'SUSPECT': 7} | 7: llama3.2:1b-instruct-q2_K, llama3.2:1b-instruct-q3_K_S, phi3.5:3.8b-mini-instruct-q2_K, qwen2.5-coder:3b-instruct-q2_K, qwen2.5-coder:3b-instruct-q3_K_L, qwen2.5-coder:3b-instruct-q3_K_M, qwen2.5-coder:3b-instruct-q3_K_S | 20 of 22 |

HumanEval/15 passes among the 305 official tags: original 0, pod rescore 134, serial 275. Official tags whose 15-task score differs from the pod rescore: 141; from the original census: 275.

Full 164-task census runs (old -> serial): qwen2.5-coder:3b-instruct-q2_K 0->0; qwen2.5-coder:3b-instruct-q3_K_S 0->0; qwen2.5-coder:3b-instruct-q3_K_M 0->0; qwen2.5-coder:3b-instruct-q3_K_L 0->0; llama3.2:1b-instruct-q2_K 0->0; llama3.2:1b-instruct-q3_K_S 6->6; phi3.5:3.8b-mini-instruct-q2_K 0->0; deepseek-coder:1.3b-instruct-q2_K 2->2; deepseek-coder:1.3b-instruct-q3_K_M 5->5; deepseek-coder:1.3b-instruct-q3_K_L 10->10; deepseek-coder:1.3b-instruct-q4_0 10->10; deepseek-coder:1.3b-instruct-q4_K_M 7->7; deepseek-coder:1.3b-instruct-fp16 16->16; llama3.2:1b-instruct-q3_K_M 41->42; llama3.2:3b-instruct-q2_K 29->30; gemma2:2b-instruct-q2_K 25->25; gemma3:270m-it-q8_0 16->16; gemma3:270m-it-fp16 20->20; gemma3:1b-it-q4_K_M 37->37; phi3.5:3.8b-mini-instruct-q3_K_S 41->42; deepseek-coder:1.3b-instruct-q3_K_S 6->7; deepseek-coder-v2:16b-lite-instruct-q2_K 24->25; mistral:7b-instruct-v0.2-q3_K_L 43->44; starcoder2:15b-instruct-v0.1-q2_K 64->65; granite-code:20b-instruct-q2_K 45->46; granite3.1-dense:2b-instruct-q2_K 16->17; yi-coder:1.5b-chat-q2_K 47->48

## Pass-to-fail

None. No previously passing instance failed serially: 0 of the 453 sampled passes, and none of the instances that passed in one existing scoring and failed in another (census HumanEval/15 and HumanEval/23 under the pod rescore) failed serially.

## Instances that still fail serially

Reasons recorded by EvalPlus for the re-evaluated failures that stay failures (base / plus): see `instances.jsonl` (`base_reason`, `plus_reason`). Counts by plus status: fail/fail: 14543, fail/pass: 121, pass/fail: 1361, timeout/timeout: 4

## Not scored

Nothing: every selected instance of every set was evaluated and no transcript is missing.

## Notes and limits

- Only the load changes for the sets first scored on this Mac (results-mac, results-metalrep,
  results-native, results-sensitivity, paper-1 tuning configurations): same machine, same EvalPlus
  install and ground-truth cache, same sanitizer, minus the pool. The census and rerun sets were first
  scored on the RunPod pod (Python 3.12.3, tree-sitter 0.26.0 / tree-sitter-python 0.25.0, numpy 2.5.2,
  Linux fork start method, the pod's own ground-truth timings). This Mac has Python 3.9.6, tree-sitter
  0.23.2 / tree-sitter-python 0.23.6, numpy 2.0.2 and the spawn start method. EvalPlus (0.3.1) and the
  datasets (HumanEval+ v0.1.10, MBPP+ v0.2.0) are the same. Evidence that the platform difference does
  not move verdicts: no sampled pass failed, every other re-evaluated failure stayed a failure, and all
  flips are failures turning into passes on five tasks with slow plus tests (by longest single plus
  test, HumanEval/130 and HumanEval/15 have the 3rd- and 5th-slowest of the 164 HumanEval+ ground
  truths). HumanEval/15 results already varied between pod scorings of the same transcripts (0 of 305
  official tags in the census, 134 in the pod rescore), and the MBPP flips occur on the same Mac install
  as their original scoring, so only the pool differs there.
- Per-instance statuses of the original scorings were not kept (the scorers wrote eval_results.json to
  a temporary directory and kept only the per-task boolean), so the old failure reason of a pod or
  census flip is unknown; the paper-1 eval_results do keep it (all their flips were plus-test failures).
- The flip diagnosis reruns the sanitized solution in a child process with EvalPlus' guard and limits
  and times each test; "max runtime / per-test limit" is the largest ratio over all tests. A value well
  below 1 means the serial pass has headroom; MBPP/160 (about 0.9) is close to its limit even serially.
- Census full 164-task runs, results-native and results-sensitivity stored only counts, so they were
  re-evaluated in full and compared at count level.
- Scope: every EvalPlus score the paper cites comes from one of the sets above, including the
  screen-tuning data from paper 1 (HumanEval+ and MBPP+). The perplexity, tensor-comparison,
  output-statistic and timing numbers are not EvalPlus scores and are not affected.
- Downstream files that still read the pool scores (paper-v3/analysis/numbers_v3.py, a1_rescored.py,
  figures) must be pointed at the `*_serial.jsonl` files before the paper can say it reports serial
  scores throughout; this script does not modify them.

## Commands

As run (2026-10-21; SERIAL_WORK pointed at a scratch directory; each command ran alone):

```
cd <scratch>/serial && export SERIAL_WORK=$PWD/work
S='.../paper-v3/analysis/serial/serial_rescore.py'
/usr/bin/python3 -E $S list
/usr/bin/python3 -E $S run metalrep      # pilot (33 instances), kept: the checkpoint resumes
/usr/bin/python3 -E $S run               # all sets in order, one process, one instance at a time
/usr/bin/python3 -E $S stability         # every flip again: 2x, or 5x if some test ran at >= 0.25 of its limit
/usr/bin/python3 -E $S report
```

Per transcript the sanitizer call is `<HOME>/Library/Python/3.9/bin/evalplus.sanitize --samples <SERIAL_WORK>/<set>/<sha1(run key)[:16]>/samples.jsonl` (164-task padded file, as the original scorers write it); its `samples-sanitized.jsonl` output is kept in the work directory.

Provenance next to this report: `instances.jsonl` (one line per serially evaluated instance: statuses, EvalPlus reasons, wall time, load average, flip diagnosis), `stability.jsonl` (repeats of flipped instances), `run_log.jsonl` (start/end per set with load averages), `serial_summary.json`.

