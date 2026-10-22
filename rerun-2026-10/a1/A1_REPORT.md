# A1: suite size and task choice for the 15-task smoke screen

Responds to BigData Reviewer 2, point 2: no justification for 15 tasks, and no comparison of suite sizes or task combinations. Everything below uses data that already exists. No model was run.

- Code: `a1_analysis.py`. Run it with `python3 -I a1_analysis.py`, or add `--tables` to print the tables below.
- Output: `a1_results.json`. It holds every number in this report, the SHA-256 of each input, and the sampling details. Two runs gave byte-identical JSON.
- Libraries: standard library only. numpy is not installed on this machine, which the script checks and records.
- RNG: seed 20261021, Python `random.Random`. Each analysis gets its own instance seeded with that value.

## Method

**Data.** The census input is `results/audit_scored.jsonl`, channel `ollama-official`: 305 artifacts with per-task results on the 15 suite tasks. Calibration uses the P1 EvalPlus results for 24 Qwen2.5-Coder configurations, scored on full HumanEval+ (164 tasks) and MBPP+ (378 tasks). A task counts as passed only if `base_status` and `plus_status` are both `pass`.

**Screening logic.** The logic comes from `analysis/analyze.py`, the code behind `findings.json` and the paper's numbers. Its grouping helpers (`size_key`, `HIGH`) are executed directly from the original source file. The script then checks itself at k = 15:

- 50 stage-one flags, the same as the paper.
- 7 suspects, the same set as `findings.json`.
- Class distribution over all 305 artifacts is identical to `findings.json`: HEALTHY 271, DEFECT_SUSPECT 7, NO_BASELINE 18, DEGRADED 3, COLLAPSED 6.

`classify.py` uses an older rule (DEFECTIVE if ratio < 0.20) that did not produce the paper's numbers, so it is not used here.

**Scaling to a k-task suite.** s is the artifact's pass count on the subset. b is the median subset pass count of its q6_K/q8_0/fp16 siblings.

| Rule | 15 tasks | k tasks (exact rationals, no rounding) |
|---|---|---|
| Stage-one flag | s < 9 | s < 0.6k (5s < 3k) |
| Healthy | s/b ≥ 0.6 | unchanged |
| Defect suspect | s ≤ 2 and b ≥ 8 | s ≤ 2k/15 and b ≥ 8k/15 (15s ≤ 2k, 15b ≥ 8k) |
| Capability collapse | s/b < 0.6 and b < 8 | s/b < 0.6 and b < 8k/15 |
| Degraded | otherwise | otherwise |

Stage two runs on flagged artifacts only. A suspect always has s < 0.6k, so every suspect is also flagged.

**Sampling.** For each k, all C(15,k) subsets are used when there are 1,000 or fewer. Otherwise the script samples 1,000 distinct subsets uniformly. Results are compared with the full 15-task suite: 50 flags and 7 suspects.

**Positives.** Two definitions are used. "4 defects" means the qwen2.5-coder:3b-instruct q2_K, q3_K_S, q3_K_M and q3_K_L builds. "5 defects" adds phi3.5:3.8b-mini-instruct-q2_K, which is under re-adjudication.

## A data problem found along the way: HumanEval/15 never passes in the census

HumanEval/15 is scored as failed for all 305 official artifacts. It also fails in all 334 rows of `audit_scored.jsonl`, which includes the community and adjudication channels. The model outputs do not explain this:

- 307 of the 334 archived census generations for this task contain the standard solution, a `join` over `range(n + 1)`. This was found by a text search, not by running the code.
- All 23 healthy calibration configurations pass HumanEval/15 in P1.
- 2 of 4 Metal-replication rows pass it.

The likely cause is in the census scoring environment, not in the models, but this has not been confirmed. As a result, the census screen in practice ran on **14 tasks that could be passed, with a bar of 9 of 14 (64%)**, not 60% of 15.

The flag set itself is unaffected: no artifact passed the task, so every score is what the screen used. The paper's statements that the suite has "15 tasks" and a "<60%" rule should be checked against this before the next submission.

The same issue explains a gap between the two runs. The 22 healthy calibration artifacts that are also in the census score 15/15 in P1 but 13 or 14 of 15 in the census. The task-level disagreements are HumanEval/15 for all 22, HumanEval/152 for 2 and HumanEval/156 for 1. None of the 22 is flagged. The defective q3_K_M scores 0/15 in both runs. qwen2.5-coder 7B q8_0 is not in the census.

## 1. Census suite-size curve (subsets of the 15 suite tasks)

How to read the table:

- \* marks k values where every subset was enumerated.
- "Bar" is the smallest score that avoids a flag, ceil(0.6k)/k. It equals exactly 60% only when k is a multiple of 5. This is why the flag counts go up and down instead of moving smoothly.
- "Recall" is the share of the 50 full-suite flags that the subset also flags.

| k | subsets | bar | flags, mean [p5, p95] | recall of the 50 | Jaccard flags, mean [p5, p95] | suspects, mean | Jaccard suspects, mean [p5, p95] | all 4 defects still suspects | all 5 still suspects |
|---|---|---|---|---|---|---|---|---|---|
| 3 | 455* | 2/3 | 56.3 [25, 134] | 0.70 | 0.52 [0.35, 0.66] | 9.1 | 0.68 [0.42, 1.00] | 1.000 | 0.971 |
| 4 | 1000 | 3/4 | 79.5 [36, 158] | 0.85 | 0.53 [0.31, 0.71] | 6.7 | 0.77 [0.50, 1.00] | 1.000 | 0.942 |
| 5 | 1000 | 3/5 | 47.6 [27, 90] | 0.72 | 0.60 [0.46, 0.72] | 6.8 | 0.83 [0.63, 1.00] | 1.000 | 1.000 |
| 6 | 1000 | 4/6 | 62.4 [35, 111] | 0.84 | 0.62 [0.44, 0.77] | 6.1 | 0.83 [0.63, 1.00] | 1.000 | 1.000 |
| 7 | 1000 | 5/7 | 76.3 [43, 123] | 0.92 | 0.61 [0.40, 0.79] | 6.2 | 0.87 [0.71, 1.00] | 1.000 | 1.000 |
| 8 | 1000 | 5/8 | 54.4 [34, 86] | 0.85 | 0.69 [0.54, 0.82] | 6.8 | 0.88 [0.63, 1.00] | 1.000 | 1.000 |
| 9 | 1000 | 6/9 | 64.7 [41, 95] | 0.92 | 0.69 [0.51, 0.84] | 6.8 | 0.92 [0.75, 1.00] | 1.000 | 1.000 |
| 10 | 1000 | 6/10 | 49.4 [34, 73] | 0.85 | 0.76 [0.63, 0.87] | 6.5 | 0.91 [0.71, 1.00] | 1.000 | 1.000 |
| 11 | 1000 | 7/11 | 57.8 [41, 80] | 0.93 | 0.77 [0.62, 0.90] | 6.5 | 0.92 [0.86, 1.00] | 1.000 | 1.000 |
| 12 | 455* | 8/12 | 66.1 [48, 85] | 0.98 | 0.75 [0.59, 0.91] | 6.4 | 0.91 [0.86, 1.00] | 1.000 | 1.000 |
| 13 | 105* | 8/13 | 52.9 [43, 63] | 0.95 | 0.86 [0.77, 0.98] | 6.3 | 0.89 [0.86, 1.00] | 1.000 | 1.000 |
| 14 | 15* | 9/14 | 59.6 [51, 65] | 1.00 | 0.85 [0.77, 0.99] | 6.1 | 0.88 [0.86, 1.00] | 1.000 | 1.000 |
| 15 | 1* | 9/15 | 50 | 1.00 | 1.00 | 7 | 1.00 | 1.000 | 1.000 |

**Confirmed defects.** The four Qwen2.5-Coder 3B defects stay suspects in every subset at every k from 3 to 15. Each of them scores 0, and the median of their 3B siblings stays above 8k/15. phi3.5 q2_K drops out in 2.9% of subsets at k = 3 and 5.8% at k = 4, and never for k ≥ 5. Those misses happen in subsets that include HumanEval/15, where the baseline from phi3.5's siblings falls below 8k/15.

**Suspects that drop out.** Only two full-suite suspects are ever lost: llama3.2:1b-instruct-q3_K_S, in 38–87% of subsets depending on k, and llama3.2:1b-instruct-q2_K, in ≤ 35%. Adjudication already cleared both as capability collapse. q3_K_S scores 2 of 15, exactly at the cap. Once 2k/15 drops below 2 (k ≤ 14), any subset that keeps both of its passed tasks takes it out of the suspect class, mostly into degraded. This is an effect of the proportional scaling, not of which tasks are in the subset. q2_K scores 0 and drops out only when the median of its siblings falls below 8k/15, which makes it a collapse.

**Suspects that appear.** Few subsets add suspects outside the full-suite set: on average 0.57 at k = 5 and ≤ 0.2 for k ≥ 9. The most frequent addition is granite3.1-dense:2b-instruct-q2_K.

**Adjudication workload.** The number of suspects that are not confirmed defects is 2.1–2.8 for k = 4–14 under the 4-defect definition, against 3 at k = 15. At k = 3 it is 5.1.

**Leave-one-out (k = 14).** Removing any one live task adds 1 to 15 flags. This comes from the stricter 9/14 bar, and every one of the 50 full flags is kept. Removing HumanEval/15 leaves the flag set exactly as it is.

**Smallest k at which a criterion holds at that k and every larger k:**

| Criterion | Smallest k |
|---|---|
| Mean flag Jaccard ≥ 0.90 | 15 |
| Mean recall of the 50 full flags ≥ 0.90 | 11 |
| All 4 defects remain suspects in ≥ 95% of subsets | 3 |
| All 5 defects remain suspects in ≥ 95% of subsets | 5 |

**Variant on the 14 live tasks only** (HumanEval/15 excluded, same procedure). All 4 and all 5 defects remain suspects in 100% of subsets at every k from 3 to 14.

| k | 3 | 5 | 8 | 10 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|
| Flags, mean | 46.1 | 40.6 | 44.8 | 41.5 | 54.2 | 44.4 | 50 |
| Jaccard flags, mean | 0.54 | 0.60 | 0.72 | 0.76 | 0.85 | 0.89 | 1.00 |
| Jaccard suspects, mean | 0.71 | 0.85 | 0.91 | 0.92 | 0.90 | 0.88 | 0.86 |

At k = 14 the flag set is identical to the census set. The only suspect lost is llama3.2:1b-instruct-q3_K_S, because the scaled cap 28/15 = 1.87 excludes s = 2.

## 2. Task choice at k = 15 on calibration data

**(a) The task pool.** The 23 healthy calibration configurations all solve 39 HumanEval+ tasks, which confirms the paper's number. The suite matches the first 15 of these 39 **in lexicographic (string) order** of task ID, so "HumanEval/107" sorts before "HumanEval/11". In numeric order the first 15 would be a different set that shares only 10 tasks with the suite. The paper should say "lexicographic".

On the suite itself, every healthy configuration scores 15/15. The known-defective qwen2.5-coder:3b-instruct-q3_K_M scores 0/15, and also 0 of all 164 HumanEval+ tasks.

**(b, c) 1,000 alternative 15-task suites from each pool.** Per-task results for the defective build are available, so its score is reported.

| Pool | Healthy min per suite, mean [p5, p95] (range) | Healthy median per suite, mean [p5, p95] | Defective score | Suites with every healthy config at 15/15 | Suites flagging ≥ 1 healthy config (< 9/15) | Healthy configs flagged per suite, mean (max) |
|---|---|---|---|---|---|---|
| 39 universally solved | 15 [15, 15] (15–15) | 15 [15, 15] | 0 in all 1,000 | 100% | 0.0% (Wilson 95% CI 0–0.4%) | 0 (0) |
| All 164 | 5.97 [3, 9] (1–11) | 10.2 [8, 13] | 0 in all 1,000 | 0% | **94.3%** (92.7–95.6%) | 6.6 (20) |

The 39-pool result holds by construction, since every healthy configuration solves every task in that pool. It shows that any 15 of the 39 would have given the same calibration result. It is not independent evidence of separation.

With random 15-of-164 suites, the 60% rule flags healthy builds at these rates:

| Size | Share of suites in which the build is flagged |
|---|---|
| 0.5B | 67–81% |
| 1.5B | 29–39% |
| 3B | 1–3% |
| 7B | 0.4–2% |

Only 5.7% of these suites separate cleanly, meaning no healthy configuration is flagged and the defect is flagged.

## 3. MBPP+ cross-check (calibration configs)

| Size (configs) | Suite (P1) | HumanEval+ pass | MBPP+ pass |
|---|---|---|---|
| 0.5B (6 healthy) | 15/15 | 74–84 / 164 (45–51%) | 146–164 / 378 (39–43%) |
| 1.5B (6 healthy) | 15/15 | 98–103 / 164 (60–63%) | 203–213 / 378 (54–56%) |
| 3B (5 healthy) | 15/15 | 127–134 / 164 (77–82%) | 229–237 / 378 (61–63%) |
| 7B (6 healthy) | 15/15 | 131–139 / 164 (80–85%) | 232–265 / 378 (61–70%) |
| 3B q3_K_M (defective) | 0/15 | 0 / 164 | 7 / 378 (1.9%) |

All 23 configurations that pass the suite reach at least 38.6% on MBPP+. Across them, HumanEval+ and MBPP+ rates are strongly correlated (Spearman 0.97).

The defective build's 7 MBPP+ passes are trivial one-line functions, such as `multiply_int` and `volume_cube`. All 24 rows are in `a1_results.json`.

## 4. Plain-language summary (for the threats/robustness section)

We checked, without new model runs, whether the screen's conclusions depend on the size of the smoke suite or on which tasks it contains. We re-ran the two-stage screen on random subsets of 3 to 14 of the 15 suite tasks, scaling the 60% bar and the defect-suspect constants to the subset size. Each of the four confirmed Qwen2.5-Coder 3B defects remained a defect suspect in every subset at every size. The phi3.5 q2_K build under re-adjudication remained a suspect in every subset of five or more tasks.

Suite size does change the stage-one queue. On average, the flagged set shares about half its members with the 15-task set at three tasks, 76% at ten and 85% at thirteen or fourteen. Part of this is arithmetic: a 60% bar can be met exactly only when the task count is a multiple of five. Stage two, which names the suspects, absorbs most of these differences.

On the calibration family, any other 15 of the 39 universally solved tasks gives the same separation, but only by construction. By contrast, 94% of random 15-task suites drawn from all 164 HumanEval+ tasks would have flagged at least one healthy configuration, mostly 0.5B and 1.5B builds. What keeps the 60% bar from flagging healthy small models is restricting the suite to tasks every healthy configuration solves, not the choice of these particular 15. Configurations that pass the suite also solve 39–70% of MBPP+.

These results do not show how the non-calibration model families would score on tasks outside the 15, because the census measured only these 15. They do not cover languages other than Python. They also do not remove the circularity of choosing tasks that the calibration family solves. Finally, one suite task (HumanEval/15) was scored as failed for every census artifact even though most archived generations contain the standard solution. The census therefore screened on 14 scoring tasks with a bar of 9 of 14, and this has to be resolved or disclosed. Excluding that task leaves the subset results essentially unchanged.
