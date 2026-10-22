# main.tex under serial scores: line-by-line diff

Checked against `paper-v3/main.tex` (700 lines, md5 `1a7d316a98859e2f172d66af8aa5c39a`, 2026-10-21 10:38). I did not edit main.tex; this file only lists the edits to make.

Sources (all in `paper-v3/analysis/serial/`):
- `numbers_serial.json`, written by `numbers_serial.py`. Keys are cited as `N.<key>`.
- `a1_serial.json`, written by `a1_serial.py`. Every subset at every k is enumerated, so all values are exact. Keys are cited as `A.<key>`.
- `figs/fig1_census.*` and `figs/fig2_calibration.*`, written by `figures_serial.py`.

All of these rest on the serial re-scoring in `*_serial.jsonl` (`SERIAL_REPORT.md`).

Line numbers refer to main.tex as it stands. Tables and figures are numbered in source order:
- Fig. 1 is the pipeline.
- Fig. 2 is the census heatmap (`figs/fig1_census.pdf`).
- Fig. 3 is calibration (`figs/fig2_calibration.pdf`).
- Table III is the classes table, Table IV attribution, Table VI sizes and Table VIII settings.

## 1. What changes, in short

Eight places change, plus three optional wording edits:
- the Fig. 1 pipeline box;
- the "scoring fault" paragraph;
- the Fig. 2 heatmap file;
- the 1.5B column of Table VI and the "12--14 of 15" sentence that cites it;
- four numbers in the RQ4 "Suite choice" bullet;
- the words "corrected scoring/scores" in three captions or sentences.

No suspect, class count, verdict, /164 score, held-out score, perplexity, Table IV cell or Table VIII cell changes.

## 2. Every change

| # | Line | Old text | New text | Source |
|---|---|---|---|---|
| 1 | 210 | `\textbf{15-task screen}\\43 flagged\\(of 305)` | `\textbf{15-task screen}\\39 flagged\\(of 305)` | `N.stage1_flags_rescored` = 39 (numbers_v3: 43; original census: 50) |
| 2 | 217 | `Counts are for the official library with corrected scoring.` | `Counts are for the official library with serial scoring.` (wording only) | -- |
| 3 | 257 | `passes it for 134 of the 305 official artifacts` | `passes it for 275 of the 305 official artifacts` | `N.he15_pass_rescored` = 275; `N.he15_pass_official` |
| 4 | 257--258 | `and one further artifact gains a different task (HumanEval/23); 135 artifacts gain one task and none loses one.` | `and one of them (deepseek-coder-v2 16B q3_K_S) also gains HumanEval/23; 275 artifacts gain a task and none loses one.` | `N.artifacts_changed_by_rescore` = 275; `N.artifacts_changed_vs_original_census`: `by_net_tasks_gained` {1: 274, 2: 1}, `tasks_gained` {HumanEval/15: 275, HumanEval/23: 1}, `any_loss` false. In the pod rescore the HumanEval/23 artifact did not also gain HumanEval/15; serially it does, so "one further artifact" no longer applies. |
| 5 | 258--260 | `The task's strengthened tests are slow and can exceed the time limit when scoring runs in parallel, so the corrected scores are lower bounds.` | `The task's strengthened tests are slow and can exceed the time limit when scoring runs in a parallel pool, so we re-scored every result serially, one evaluation at a time with EvalPlus's default limits; serially the task runs at 0.09--0.18 of its limit.` | `SERIAL_REPORT.md` flips table (HumanEval/15 max runtime / per-test limit 0.09 / 0.11 / 0.18). The "lower bounds" clause no longer applies; see §3 Q1. |
| 6 | 260 | `The correction reduces stage-one flags from 50 to 43` | `The correction reduces stage-one flags from 50 to 39` | `N.stage1_flags_original` = 50, `N.stage1_flags_rescored` = 39 |
| 7 | 260--261 | `and leaves every class count and all seven suspects unchanged.` | Keep as is, which is still literally true, or add: `(two non-suspect tags swap between healthy and degraded)`. | `N.classes_rescored` = {HEALTHY 271, DEGRADED 3, COLLAPSED 6, SUSPECT 7, NO_BASELINE 18}; `N.class_changes_vs_original_census`; see §3 Q2 |
| 8 | 261 | `We report corrected scores throughout.` | `We report serially re-scored results throughout.` (see §3 Q6 for a more exact version) | -- |
| 9 | 334 | `(corrected scores). All six low-baseline tags, ...` | `(serial scores). All six low-baseline tags, ...` Wording only; the rest of the caption and every cell of Table III (lines 341--345: 271 / 3 / 6 / 7 / 18) are unchanged. | `N.classes_rescored`, `N.deepseek_coder_1.3b` |
| 10 | 352--353 | `\includegraphics[width=\textwidth]{figs/fig1_census.pdf}`, caption `15-task suite score (of 15, corrected scoring)` | Use `analysis/serial/figs/fig1_census.pdf`, and change the caption to `(of 15, serial scoring)`. The rest of the caption is unchanged. | 141 of the 305 cells rise by 1 against the current figure, all from HumanEval/15 (`N.artifacts_changed_vs_numbers_v3`). Cells below 9: 39. |
| 11 | 495 | `(Table~\ref{tab:sizes}: 12--14 of 15)` | `(Table~\ref{tab:sizes}: 13--15 of 15)` | `N.table_VI_text.1.5B_library_and_plain_range` = [13, 15]. The library and plain cells of the 1.5B column; the old range 12--14 also covered exactly those cells. |
| 12 | 518 | `\texttt{q2\_K} & 12 / 12 / 11 & 0 / 0 / 15` | `\texttt{q2\_K} & 13 / 13 / 12 & 0 / 0 / 15` | `N.table_VI_sizes.q2_K` (G1 serial: g1lib, g1plain, g1imat) |
| 13 | 519 | `\texttt{q3\_K\_S} & 14 / 14 / 13 & 0 / 0 / 2` | `\texttt{q3\_K\_S} & 15 / 15 / 14 & 0 / 0 / 2` | `N.table_VI_sizes.q3_K_S` |
| 14 | 520 | `\texttt{q3\_K\_M} & 14 / 14 / 14 & 0 / 0 / 9` | `\texttt{q3\_K\_M} & 15 / 15 / 15 & 0 / 0 / 9` | `N.table_VI_sizes.q3_K_M` |
| 15 | 521 | `\texttt{q3\_K\_L} & 14 / 14 / 13 & 0 / 0 / 7` | `\texttt{q3\_K\_L} & 15 / 15 / 14 & 0 / 0 / 7` | `N.table_VI_sizes.q3_K_L`. The 3B column is unchanged; the census 1.5B tags score the same as g1lib (13 / 15 / 15 / 15, `1.5B_census_tag`). |
| 16 | 606 | `On the corrected census scores, every subset of 5 or more of the 15 tasks keeps the five rebuilt suspects in the suspect set.` | `On the serially re-scored census scores, every subset of 3 or more of the 15 tasks keeps the five rebuilt suspects in the suspect set.` | `A.headline.k_with_all_5_rebuilt_kept_in_100pct_of_subsets` = 3..15; `A.headline.count_all_5_rebuilt_suspects` = all 32,647 subsets; phi3.5 q2_K never drops out (`A.headline.phi35_q2K_dropout_by_k` = {}); see §3 Q3 |
| 17 | 606 | `drops out of 32--87\% of subsets at every size from 3 to 14` | `drops out of 31--87\% of subsets at every size from 3 to 14` | `A.headline.llama_q3_K_S_dropout_range_k3_14` = [0.308 (k = 8), 0.8667 (k = 14)]; nonzero at every k = 3..14 |
| 18 | 606 | `and \texttt{q2\_K} drops out of at most 25\%, only at 8 or fewer tasks` | `and \texttt{q2\_K} drops out of at most 22\%, only at 8 or fewer tasks` | `A.headline.llama_q2_K_dropout_max` = 0.2154 (k = 4); `llama_q2_K_dropout_nonzero_k` = 3..8 |
| 19 | 606 | `a mean Jaccard index of 0.61 at 5 tasks and 0.77 at 10` | `a mean Jaccard index of 0.63 at 5 tasks and 0.78 at 10` | `A.headline.mean_jaccard_flags_k5` = 0.632, `mean_jaccard_flags_k10` = 0.778. These are exact; the released 1000-draw settings on serial scores give 0.631 and 0.780, which round the same. |
| 20 (optional) | 317 | `Scoring & EvalPlus 0.3.1, HumanEval+ plus-tests \\` | `Scoring & EvalPlus 0.3.1, HumanEval+ plus-tests, scored serially with default time limits \\` | wording |
| 21 (optional) | 672 | `The HumanEval/15 scoring fault shows that harness errors happen; correcting it changed no verdict.` | `The HumanEval/15 scoring fault shows that harness errors happen; re-scoring every result serially changed no suspect or attribution verdict.` | see §3 Q2 |
| 22 (optional) | 606 | `mostly because the cap scaled to $2k/15$ ... falls below its subset score` | Unchanged; still true. | `A.llama_dropout_reasons`: 94.1% of q3_K_S drop-outs have the score above the cap. All q2_K drop-outs come from the group baseline falling below 8k/15. |

For the "scoring fault" paragraph, here is lines 255--261 with changes 3--8 applied, ready to paste. It is 104 words against the current 105:

> \emph{A scoring fault, corrected.} The census scorer marked HumanEval/15 as failed for every artifact,
> although most generations contain the standard solution. Its strengthened tests are slow and can exceed
> the time limit when scoring runs in a parallel pool, so we re-scored every result in this paper serially,
> one evaluation at a time with EvalPlus's default limits. HumanEval/15 then passes for 275 of the 305
> official artifacts, one of which also gains HumanEval/23; no task passed before fails now. The correction
> reduces stage-one flags from 50 to 39 and leaves every class count and all seven suspects unchanged. We
> report serially re-scored results throughout.

## 3. Qualitative claims to check

- **Q1. L259--260, "so the corrected scores are lower bounds": no longer holds.** Serially, HumanEval/15 runs at 0.09--0.18 of its per-test limit, and every flip passed 2--5 serial repeats. The scores are no longer limited by load, so the clause should go (change 5).
  - Two MBPP+ tuning flips still run close to the limit serially (Mbpp/160 at 0.91, Mbpp/392 at up to 0.79). They do not move any number the paper prints (Q5).

- **Q2. L260--261 "leaves every class count ... unchanged" still holds; class membership does not.** Two non-suspect tags swap, against both numbers_v3 and the original census (`N.class_changes_vs_numbers_v3`):
  - mistral:7b-instruct-v0.2-q8_0 goes HEALTHY → DEGRADED. Its score stays 6 of 15. Its group baseline rises from 10.0 to 10.5 (original census: 9.5), because its high-precision siblings gain HumanEval/15. The ratio is now 0.571.
  - yi-coder:1.5b-chat-q2_K goes DEGRADED → HEALTHY. It scores 9 (pod and original: 8) against a baseline of 15 (was 14), a ratio of exactly 0.600.
  - Counts stay 271 / 3 / 6 / 7 / 18 only because the two moves offset. analyze.py merges mistral v0.1, v0.2 and v0.3 into one "mistral/7" group.
  - One of the three DEGRADED tags is now an 8-bit tag. The degraded set is granite3.1-dense:2b-instruct-q2_K, llama3.2:3b-instruct-q2_K and mistral:7b-instruct-v0.2-q8_0. The paper never says degraded tags are low-bit, so no sentence becomes false.
  - L672 "correcting it changed no verdict": true for suspects and attribution verdicts, but two stage-two classes change. Optional change 21 makes this exact.

- **Q3. L606 "every subset of 5 or more": now "every subset of 3 or more"; the claim gets stronger.** With every subset enumerated, all five rebuilt suspects stay suspects in all 32,647 subsets of 3 to 15 tasks.
  - The phi3.5 q2_K drop-outs on the pod scores (0.2% at k = 3, 0.9% at k = 4) came from its q6_K, q8_0 and fp16 siblings failing HumanEval/15 under the pool. Serially they pass it, so the sibling median never falls below 8k/15.
  - L109 "robust to suite size ... for the five rebuilt failures" still holds, more strongly.

- **Q4. L606: the llama3.2-1B pattern is unchanged.** q3_K_S still drops out at every size from 3 to 14, mostly through the scaled cap. q2_K still drops out only at k ≤ 8.

- **Q5. These still hold** (source key in parentheses):
  - "all low-baseline or no-baseline tags" for the six false positives of the either ≥ 0.3 rule, L558 (`N.rq3_output_rules.either_ge_0.3.fp_classes` = COLLAPSED 4, NO_BASELINE 2).
  - "none loses one", L258 (`any_loss` false).
  - "seven non-functional artifacts is a lower bound", L377, which is about deepseek-coder-1.3B, not scoring.
  - "the deepseek-coder-6.7B and starcoder2-15B tags ... work", L375--376 (`N.pretokenizer_other_14`: all 14 score ≥ 9; 11 healthy, 3 no baseline).
  - "All six low-baseline tags, and six of the healthy ones, are deepseek-coder-1.3B tags scoring 1 to 6", L334--335 (`N.deepseek_coder_1.3b`: COLLAPSED 6, HEALTHY 6 with scores 3--6).
  - "None of the other 257 tags is a suspect", L366.
  - "the Qwen2.5-Coder-3B column ... recovers at 4 bits", L355 (q4_0 = 15).
  - "a handful of code tasks catches every failure reported here", L658.

- **Q6. Wording caution for "we report serially re-scored results throughout".** By design, the serial pass re-evaluated:
  - every instance that failed in any scoring;
  - every instance of the sets that stored only counts (census full-164 runs, results-native, results-sensitivity);
  - a seeded 3% sample of the remaining passes. All 453 sampled passes still passed.

  The other passes were carried over from the pool scoring, on the reasoning that load can only turn passes into time-outs, not the reverse. If the paper should say exactly what was done, use: "every failure, and a 3\% sample of passes, was re-evaluated serially; no pass changed".

- **Q7. L605, the miss-audit frame.** "frame set before the scoring correction" and "the 233 tags in that frame" stay correct: the frame is the 255 tags unflagged on the original census minus 22 tuning configurations (`N.miss_audit_frame`).
  - Serially, 244 non-tuning tags pass the screen (numbers_v3: 240), and 5.5% of 244 is 13.4. "about 13 artifacts" still holds whichever population is meant.
  - Every tag in the frame is also unflagged serially, because serial scoring only adds passes.

- **Q8. Platform.** The census and rerun transcripts were first scored on the pod (Python 3.12, tree-sitter 0.26 / 0.25). The serial scores come from this Mac (Python 3.9.6, tree-sitter 0.23), with the same EvalPlus 0.3.1, HumanEval+ v0.1.10 and MBPP+ v0.2.0. L256--257 "with the same EvalPlus version" remains accurate. Across about 16,000 re-checked failures, no verdict moved other than the load-sensitive flips.

## 4. Numbers checked that do not change

Each line below names the number in the text, then the source key in `numbers_serial.json` (N) or `a1_serial.json` (A) that confirms it.

**Abstract**
- L36--37: 327 artifacts (313 quantized), 305 tags, 15 model lines, 22 Hugging Face files. Census counts, `N.census`.
- L39--40: seven artifacts (2.3%) solve at most 6 of 164. `N.nonfunctional`, `N.full164.derived.suspects_max` = 6.
- L43: 0 → 76--113 of 164. `N.full164.derived.own_imatrix_three_rescued_range` = [76, 113].
- L44--45: phi3.5 0 → 21 → 37. `N.full164.phi35`.
- L45--46: the 1.5B model is functional. `N.table_VI_sizes`.
- L46--47: none of 66, 95% upper bound 5.5%. `N.fn_audit`.

**Introduction**
- L70: 26 of 305 tags lack a pre-tokenizer type. Not a score.
- L90: 46--69%. `N.full164.derived.own_imatrix_three_rescued_pct` = [46.3, 68.9].
- L106: 305, 291, 22.
- L108: 46--69%; 80% for the 4-bit tag (`registry_qwen_4bit_pct` = 80.5).
- L109: 66 artifacts; about 30 s (`N.screen_seconds.median` = 30.2).

**Fig. 1 (pipeline)**
- 305 + 22; 7 suspects; 164 tasks (CUDA); 15 tasks on Metal; 5 suspects rebuilt; 49 audit tasks.

**Study design**
- L226--229: 305 = 291 + 14 fp16; 29 groups; 22 files from 12 repositories.
- L233--240, from `N.tuning_serial`:
  - 24 configurations and 23 healthy;
  - 39 tasks solved by all healthy configurations, and the first 15 lexicographically are the suite;
  - every healthy configuration passes 15 of 15, and the known failure passes none.

  The tuning HumanEval+ per-task results are identical serially: `A.calibration_94pct_check.humaneval_per_task_differences_serial_vs_pool` = {}.
- L242, L252, L278--279: rule constants (9 of 15; 10% of 164; 2, 5, 4 of 15).
- Table II (L312--321): configuration only.

**RQ1**
- Table III (L341--345): 271 / 3 / 6 / 7 / 18. `N.classes_rescored`.
- Table III caption: six low-baseline and six healthy deepseek-coder-1.3B tags, scoring 1--6. `N.deepseek_coder_1.3b`.
- Fig. 2 caption (L353--356): 305 artifacts, seven suspects, four adjacent zero levels, 1--6 for deepseek-coder-1.3B including fp16.
- L360--361: six solve 0 of 164 and llama3.2-1B q3_K_S solves 6. `N.full164.suspects`.
- L362--364: 7 of 305 (2.3%; Wilson 1.1--4.7%) and 3 of 29 (10.3%; 3.6--26.4%). `N.nonfunctional`, `N.nonfunctional_groups`.
- L365--366: 48 low-bit tags in models of at most 4B; 257 others. `N.lowbit_le4b`.
- L367: 20 of 22 Hugging Face files healthy. `N.community_healthy_cuda` = 20.
- L369--370: the 12 deepseek-coder-1.3B tags score 1--6; fp16 solves 16 of 164. `N.deepseek_coder_1.3b`.
- L371--374: 59%, 2.4%, 286, and 6--8% of prompt tokens. Parse and tokenizer statistics, not EvalPlus scores (286 = 305 − 12 − 7).
- L385--386: 2.3%; three of 29.

**RQ2**
- Table IV (L407--413): every cell is unchanged (`N.table_IV_attribution`):
  - Library: 0, 0, 0, 0, 0, 0, 2.
  - Library /164: 0, 0, 0, 0, 0, 0, 6.
  - Plain: 0, 0, 0, 0, then 0 (4) for phi3.5.
  - Own imatrix: "15, 15", "2, 4", "9, 8", "7, 8", "9, 8".
  - Third party: 15, 4, 10, 9, 7, (1), (4).
  - Qwen AWQ: 14 and 15.
  - Best cal. /164: 113, 30, 125, 86, 37.
- Table IV caption: 21 of 164; 9 and 8 against 4; 7 against 0. `N.table_IV_caption`.
- Fig. 3 caption (L421--428): 0 of 164, 21, 37, 34, and 8 of 15 for the phi3.5 code-imatrix build (`N.P0_smoke.codeimat-phi35-Q2_K`). Fig. 3 data are unchanged; only its layout changed (§5).
- L456--463: 434, 197 and 32 tensors (not scores). The library-mix rebuild scores 0 of 15 and 0 of 164. Plain Q4_K_M and Q6_K score 15 of 15, and Q4_K_M 129 of 164. Perplexity 11.60 against 11.55.
- L473--482:
  - own-imatrix ranges 106--113, 76--89 and 80--86 (`N.full164.derived`);
  - phi3.5 21 → 37, exact McNemar p = 0.007 (`N.mcnemar_phi35_plain_vs_wikitext`: 8 tasks only plain, 24 only imatrix, p = 0.007);
  - bartowski phi3.5 34; bartowski Qwen 104, 81, 77; AWQ 102 and 125;
  - 435 against 434 tensors;
  - Qwen q3_K_S stays at 13--30 under every calibration;
  - calibrated builds at 7 or 8 of 15;
  - registry 4-bit tags: 132 (Qwen) and 74 (phi3.5).
- L484--490: 1.3× and 6× fp16 perplexity; 106--113; perplexity within 4%.
- L495--496: 338 tensors; the 1.5B q2_K tag solves 10 of 49 against 28 for q4_0 (`N.heldout_1p5b`; q3_K_S solves 23).
- L497--501: 896-wide rows, 256-weight blocks, 96--144 of 169 matrices, 5.4--5.9 bits per weight (not scores). The 3B q4_0 tag (1.8 against 1.7 GB) scores 15 of 15 (`N.table_VI_text.qwen3b_q4_0_tag_15`).
- Table VI, 3B column: 0/0/15, 0/0/2, 0/0/9, 0/0/7.
- L537: unsloth files score 1 and 4 of 15. `N.community_serial.hf_adjudication`.
- L542--544:
  - TheBloke files score 5 and 6 on CUDA and 13 and 15 on Metal;
  - the Ollama tags of the same model score 14 and 14 (`N.community_serial`, `N.metal_serial`);
  - 87% and 94% of their generations hit the token cap (truncation, not a score).

**RQ3**
- L555--560, from `N.rq3_output_rules`:
  - truncation ≥ 0.2 catches 3 of 7, with 10 false positives;
  - repeated 6-grams ≥ 0.2 catch 3, with 4 false positives;
  - either statistic ≥ 0.3 catches 4, with 6 false positives (2.0%), all low-baseline or no-baseline;
  - the three missed tags never hit the token cap;
  - the lowest repetition bar that catches any of them fires on 12 of 271 healthy tags (4.4%). Catching all three would fire on 196 of 271 (72%).
- L563--572: perplexity ratios 27--5,700×, 4.2% and 5.1%, 10--25×, 18.6× and 18.8× (not scores); the calibrated Qwen Q3_K_M build solves 76 of 164 (`N.R6`).
- Table VII: perplexity only.
- L597: four of seven.

**RQ4**
- L604: seven suspects, at most 6 of 164.
- L605:
  - ten strata, 49 tasks;
  - 66 audited (10 + 56), none at or below 2 of 49;
  - the new ones range from 8 to 41 (`N.fn_audit`: min 8, max 41, median 21.0, misses 0). The one changed run, deepseek-coder 6.7B q4_0, goes from 29 to 30 and changes none of these. The first version's 10 range 11--29 and do not change;
  - 27.8% → 5.5%;
  - 233 tags in the frame; about 13 artifacts (`N.miss_audit_frame`).
- L606: 94% (`A.headline.calibration_94pct` = 0.943; part 2 is identical to the released A1).
- L607: the five library suspects and plain Qwen Q2_K and Q3_K_M score 0; the 4-bit tags stay healthy; plain phi3.5 at the current mix scores at most 4. `N.table_VIII_settings`.
- Table VIII (L622--627): every cell is unchanged:
  - the library Qwen 3B q2_K--q3_K_L rows, library phi3.5 q2_K, and plain Qwen Q2_K and Q3_K_M score 0 in every setting;
  - plain phi3.5 scores 4 / 4 / 0 / 2 / 3, 4, 3;
  - library Qwen q4_K_M scores 15 throughout;
  - library phi3.5 q4_K_M scores 11 / 11 / 11 / 9 / 11, 11, 11.
- L608: 12 to 105 s, median 30 s. `N.screen_seconds`.
- L632--633: seven; 6 of 164; 66; half a minute.

**Discussion, threats and conclusion**
- L640: about 30 s.
- L653--655: two of four AWQ levels.
- L663--665: "about two thirds" (106--113 of 164 = 65--69%).
- L671: on MBPP+, the 23 healthy configurations solve 39--70% of 378 tasks and the known failure solves 7.
  - Serially the range is 38.6--70.1%, the same as before (`N.tuning_serial`; `A.calibration_94pct_check.mbpp_healthy_rate_range_pct_serial`).
  - Nine MBPP+ instances in 8 healthy configurations flip to pass, but neither end of the range moves.
  - Same line: 4 against 9 of 15; 0 → 34; 21 → 37.
- L672: the five rebuilt suspects score 0 of 15 on both CUDA and Metal. `N.metal_serial.five_rebuilt_suspects_zero_on_metal`.
- L673: seven is a lower bound.
- L678--681: seven of 305; three of four levels; half to two thirds; about 30 s; 66.

## 5. Figures

- **`figs/fig1_census.pdf` / `.png`** (Fig. 2, census heatmap):
  - It uses serial per-task scores: 141 cells rise by 1 against the current paper figure, and 39 cells are below 9.
  - The asserts hold: 305 cells, each artifact once, unique labels, 15 lines, and the seven suspects boxed with their serial scores. The flag count now must equal `N.stage1_flags_rescored` = 39.
  - Layout: FS = MIN_PT = 8 pt; drawn at the 516 pt text width (7.14 in, the old figure assumed 7.16 in); LEFT, RIGHT = 0.47, 0.03; LAB_H = 1.10.
  - The key text is now "15-task suite: tasks passed"; the suspect key moved right by 0.23 in (gap 1.62 → 1.85 in).
  - I checked the PNG: nothing overlaps and no text is clipped.
- **`figs/fig2_calibration.pdf` / `.png`** (Fig. 3):
  - Data are unchanged; the asserts still read 0, 21 and 37.
  - Layout: FS = MIN_PT = 8 pt; two-column legend; L2, R2, B2, T2 = 0.46, 0.02, 0.32, 0.66.
  - At 8 pt the "37" label touched the right end of the phi3.5 "current mix" bracket. I raised both brackets from y = 52 to y = 56 and added the brackets to the layout check's collision boxes; a test run confirmed the check fails at y = 52.
  - I checked the PNG: nothing overlaps.
- The check now reports every text element at ≥ 8.0 pt at final size for both figures.
- The paper still includes `figs/fig1_census.pdf` and `figs/fig2_calibration.pdf`. Point the includes at `analysis/serial/figs/` or copy the files over; I did not touch `figs/`.
