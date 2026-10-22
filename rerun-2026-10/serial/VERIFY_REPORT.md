# Adversarial verification of the serial re-scoring

Checked 2026-10-21 against `paper-v3/main.tex` (md5 `1a7d316a98859e2f172d66af8aa5c39a`, 700 lines), the files in
this folder (`SERIAL_REPORT.md`, `PAPER_DIFF.md`, `*_serial.jsonl`, `numbers_serial.json`, `a1_serial.json`,
`figs/`) and the raw sources. Nothing in main.tex, references.bib, figs/ or any raw data file was changed. My
scripts and outputs are in the scratch folder
`<SCRATCH>`
(called `verify/` below).

## Verdict

**The data and numbers are correct; the proposed paper edits need four corrections.**

- Every verdict I re-evaluated serially agrees with the serial files: 104 of 104 instances, and 7 of 7 whole
  transcripts run through the original CLI path with one worker.
- I recomputed every printed number independently from `*_serial.jsonl` and got the same values as
  `numbers_serial.json`, `a1_serial.json` and PAPER_DIFF.md. That covers stage-one flags, classes, suspects,
  Tables IV, VI and VIII, the /164 numbers, McNemar, held-out, tuning, MBPP+, RQ3 and A1.
- The regenerated figures match the serial data cell for cell and print every text at 8.0 pt.
- The problems are in the instructions for the paper, not in the data (section 6):
  1. pointing the includes at `analysis/serial/figs/` breaks the arXiv build;
  2. the paste-ready paragraph claims every result was re-scored serially, which overstates what was done;
  3. L672 "changed no verdict" must be qualified, because two stage-two classes change;
  4. two documentation points in SERIAL_REPORT.md need correcting.

## 1. Independent serial re-evaluation

**Method** (`verify/verify_eval.py`, `verify/make_selection.py`, seed 4242):
- Each transcript or solution was located from the raw sources, not from `*_serial.jsonl`:
  - `census_rescore.jsonl` plus `results/pod_archive/results/transcripts`;
  - `pod-results/results-*/runs.jsonl`;
  - `results-*/audit_results.jsonl`;
  - paper-1 `*_eval_results.json`.
- Each was padded to 164 tasks with the scorer's own placeholder and passed through the `evalplus.sanitize`
  CLI in a fresh directory.
- Each instance was evaluated with `evalplus.evaluate.check_correctness`, one at a time, at EvalPlus default
  limits (EvalPlus 0.3.1, HumanEval+ v0.1.10 hash fe585eb4…, MBPP+ v0.2.0).
- Every failure was re-run with generous limits (20 s minimum per test, 40× ground truth) to separate
  wrong-output failures from time-limit failures.
- 1-minute load average during my runs was 1.9 to 3.5. This Mac idles at about 2.0 with nothing heavy running.

**Sample: 104 instances, all 17 sets covered.**

Flipped or gained instances (46):

| Set | Task | Instances |
|---|---|---|
| census_smoke | HumanEval/15 | 24 (fail→pass) |
| rerun_g1 | HumanEval/15 | 8 |
| census_full164 | HumanEval/15 | 3 (count-level flips) |
| rerun_r3 | HumanEval/130 | 1 |
| tuning_p1_mbpp | Mbpp/392 | 7 |
| tuning_p1_mbpp | Mbpp/599 | 1 |
| tuning_p1_mbpp | Mbpp/160 | 1 |
| census_smoke | HumanEval/23 | 1 (deepseek-coder-v2 16B q3_K_S: failed in the original census, passed in the pod rescore) |

Unflipped failures (58):
- 15 still-failing HumanEval/15 instances, including the "fail at test 79" one;
- 3 instances that time out serially;
- 6 failures on the slow tasks;
- 34 random failures, 2 per set.

**Results:**
- Agreement with the serial verdict is 104 / 104: 46 pass and 58 fail.
- The base/plus statuses also match for all 58 failures: fail/fail 54, timeout/timeout 3, pass/fail 1.
- My sanitized solution is byte-identical to the serial agent's work-dir copy in 89 / 89 cases. The other 15
  are tuning instances, which use stored solutions.
- None of the 58 failures passes with 20 s per test and 40× limits, so none is a load or time-limit artifact.
- `mistral:7b-instruct-v0.2-q8_0` HumanEval/15 decides that tag's class (section 3). It is a genuine
  failure: the generation is a bare `return …` with no `def`.

**Whole-transcript check through the original code path** (`verify/cli_run.py`): `evalplus.sanitize` and then
`evalplus.evaluate --parallel 1`, one transcript at a time. Per-task results equal the serial files in all 7:

| Set / run | CLI | serial | pool (old) |
|---|---|---|---|
| census mistral:7b-instruct-v0.2-q8_0 | 6 | 6 | 6 |
| census yi-coder:1.5b-chat-q2_K | 9 | 9 | 8 |
| census deepseek-coder-v2:16b-lite q3_K_S | 15 | 15 | 14 |
| rerun_g1 g1lib-qwen1.5b-q2_K | 13 | 13 | 12 |
| rerun_r3 fn-deepseek-coder 6.7b q4_0 (heldout49) | 30 | 30 | 29 |
| census_full164 yi-coder:1.5b-chat-q2_K | 48/164 | 48 | 47 |
| census_full164 granite3.1-dense:2b q2_K | 17/164 | 17 | 16 |

An earlier timing run of census qwen2.5-coder:0.5b q3_K_S also gave 13/15 = serial, and its padded and
sanitized files are byte-identical to the agent's.

**Remaining failures that could be time-limit failures.** A serial check that took ≥ 1.4 s is the only kind
that can have hit a per-test limit of at least 1 s. The non-tuning sets have 133 such failures. I re-ran all 133, one at a time (`verify/slowfail3.py`), at the
default limits and at doubled limits (2 s minimum per test, 8× ground truth).

| Check | Result |
|---|---|
| Fail at default limits, status equal to the serial status | 133 / 133 |
| Fail at doubled limits | 133 / 133 |
| Sanitized code byte-identical to the agent's | 133 / 133 |

The wall times sit at the per-test limit, about 2.5 s at default and 4.5 s doubled. These solutions do not
finish a test even in twice the allowed time, so they are not near-limit cases.

- An outside load spike (up to 11.0, not from my jobs) hit 17 of these checks. I re-ran those 17 at load 1.9–2.6
  and got the same result (`slowfail3_hiload_redo.jsonl`).
- A first attempt (`INVALID_slowfail*_no_main_guard.jsonl`) is void and not used. Its script lacked an
  `if __name__ == "__main__"` guard, so with macOS spawn every child process failed to start and every check
  read "timeout".

So the remaining census and rerun failures are not load or time-limit artifacts, and dropping "lower bounds"
is justified.

## 2. Sanitizing and serial execution

**Sanitizing matches the original scorers.**
- Placeholders:
  - `pass  # placeholder-unattempted` for score_smoke.py and score_runs.py (census_smoke, rerun_*, mac, metalrep);
  - `pass` for fullrun.py and score_experiments.py (census_full164, native, sensitivity).
- All use the same 164-task padding order (`get_human_eval_plus()` keys), "a later line wins" transcript
  reading, and the `evalplus.sanitize` CLI with a fallback to the raw file.
- Paper-1 tuning uses the stored sanitized `solution` field, which is exactly what `evalplus.evaluate` evaluated.
- `check_correctness` gets the arguments `evaluate()` passes:
  - `base_only=False`;
  - `fast_check=not test_details=True`;
  - default `min_time_limit` and `gt_time_limit_factor`;
  - the local ground-truth cache.
- The census transcripts in `results/pod_archive` are byte-identical to the serial agent's extraction of
  `results/audit_data_full.tgz` (361 / 361 files).
- The rerun `runs.jsonl` files have no duplicate key that points to a different transcript.

**No evaluation ran in parallel.**
- `instances.jsonl` holds 17,581 records written by one process. Timestamps are monotonic, and no record
  starts before the previous record's start plus its wall time (0 overlaps).
- `stability.jsonl` (414 repeats, all pass) ran after the main run (14:26–14:55 against 10:47–14:23), also
  with 0 overlaps.
- My own evaluations ran strictly one after another. Alongside them ran only file reads and parsing scripts of
  a few seconds each; the A1 enumeration ran between evaluation batches.

**Platform (not load) differences remain for the sets first scored on the pod** (Python 3.12.3 →
3.9.6, tree-sitter 0.26 → 0.23, Mac ground-truth timings). I looked for an effect and found none:
- A static scan of all 10,476 remaining non-tuning failures found no Python ≥ 3.10 syntax (`match`,
  PEP 701 f-strings, parenthesized `with`).
- The 8 matches for 3.10+ APIs or `X | Y` annotations are either wrong code (for example a docstring-only
  function) or instances that already failed on the pod.
- By construction, the per-task sets only re-evaluate pod failures.
- The count-only census_full164 counts for the runs the paper cites are equal on pod and Mac: suspects 0 and
  6, deepseek-1.3B fp16 16.

## 3. Independent recomputation (`verify/recompute.py`)

All checks pass (`verify/recompute_out.json`, 79 checks, 0 differences):

**Census and stage one**
- Stage-one flags: 39 serial, 43 pod, 50 original.
- Flags leaving against pod: llama3.2:1b q4_K_M, mistral:7b q4_0, phi3.5 q3_K_S and yi-coder:1.5b q2_K. No new flags.
- HumanEval/15 passes among official tags: 275 serial, 134 pod.
- Against the original census, 275 artifacts change: 274 gain 1 task, and 1 gains 2 (deepseek-coder-v2 16B q3_K_S,
  HumanEval/23). 0 tasks are lost.
- Against pod, 141 artifacts change, all on HumanEval/15, and none loses a task.

**Classes**
- Counts: 271 healthy, 3 degraded, 6 low baseline, 7 suspect, 18 no baseline. The seven suspects are unchanged.
- Two swaps, against both pod and original:
  - mistral:7b-instruct-v0.2-q8_0 goes HEALTHY→DEGRADED. Its score stays 6; the mistral/7 baseline goes
    10.0→10.5 (ratio 0.571).
  - yi-coder:1.5b-chat-q2_K goes DEGRADED→HEALTHY. It scores 9 against a baseline of 15 (ratio 0.600).
- Original → pod had 0 class changes.

**Text numbers**
- deepseek-1.3B: scores 1–6, 6 low baseline and 6 healthy; fp16 16/164.
- deepseek-6.7B and starcoder2 tags: all 14 score ≥ 9.
- Ollama deepseek-6.7B q3_K_M and q4_K_M: 14 and 14.
- TheBloke files: 5 and 6 on CUDA, 13 and 15 on Metal. unsloth files: 1 and 4.
- Community: 20 of 22 at ≥ 9.

**/164 and calibration**
- Suspects /164: 0,0,0,0,0,0 and 6.
- Own imatrix: 106/113, 76/89, 80/86. bartowski: 104, 81, 77. AWQ: 102, 125. Q3_K_S calibrated: 13–30.
- 4-bit tags: 132 and 74. Plain Q4_K_M: 129, with 15/15 for Q4_K_M and Q6_K.
- phi3.5: 0 / 21 / 37 / 34, code imatrix 8/15.
- McNemar for phi3.5 plain vs WikiText: 8 vs 24, exact p = 0.007.

**Tables**
- Table IV: every cell as printed.
- Table VI:
  - 1.5B column: 13/13/12, 15/15/14, 15/15/15, 15/15/14;
  - 3B column unchanged;
  - library and plain range 13–15;
  - census 1.5B tags 13/15/15/15.
- Table VIII: every cell as printed, and every multi-build row is 0 for every build.

**Miss audit, Metal and tuning**
- Miss audit: 56 new scoring 8–41 with 0 at ≤ 2; the first version's 10 score 11–29.
- 1.5B held-out: q2_K 10 and q4_0 28.
- Metal: the five rebuilt suspects score 0.
- Tuning: 24 configurations, 23 healthy, pool of 39 tasks, suite = first 15 lexicographic, all healthy
  configurations 15/15, defective 0.
- MBPP+: 39–70% of 378, defective 7.

**RQ3** (healthy set after the swap)
- Truncation ≥ 0.2: 3 hits, 10 false positives.
- rep6 ≥ 0.2: 3 hits, 4 false positives.
- Either ≥ 0.3: 4 hits, 6 false positives (2.0%), all low baseline or no baseline.
- Lowest bar catching one missed tag: 12/271 healthy (4.4%).

**A1, exact enumeration of all 32,647 subsets, k = 3..15** (`verify/recompute_a1.log`)
- The five rebuilt suspects are suspects in every subset at every k ≥ 3.
- Mean flag Jaccard: k=5 0.632, k=10 0.778.
- llama3.2-1B q3_K_S drops out at every k from 3 to 14, at 30.8% (k=8) to 86.7% (k=14).
- llama3.2-1B q2_K drops out at most 21.5% (k=4), and only at k = 3..8.
- phi3.5 q2_K never drops out.

**Heatmap**
- 39 cells below 9; 141 cells +1 against the current figure; all other cells unchanged.

## 4. PAPER_DIFF.md line by line

**Correct as written:**
- Rows 1, 3, 4, 6, 9, 11–19.
- The values cited in §4 ("numbers that do not change").
- Q1, Q2, Q3, Q4, Q5, Q7 and Q8.

**Rows 2, 8 and 20:** wording only, fine.

**Row 5 and the paste-ready paragraph: problem 2.** They say "we re-scored every result (in this paper)
serially". That contradicts PAPER_DIFF's own Q6: only every failure (and every task of the three count-only
sets) plus a 3% sample of passes was re-evaluated, and 14,462 passes were carried over. Use the paragraph in
section 7.

**Row 7:** keep the sentence, and disclose the swap, as the paragraph in section 7 does.

**Row 10: problem 1.** See section 6.

**Row 21:** should be applied, not optional (problem 3). PAPER_DIFF's text again says "re-scoring every
result serially"; use the text in section 7.

**Missed numbers:** I searched main.tex for every score-derived number and every occurrence of "corrected",
"correction", "parallel", "lower bound", 43, 50, 134 and 135. Nothing outside PAPER_DIFF's list depends on
the serial change.
- L605 "frame set before the scoring correction" stays true.
- L377 and L673 "lower bound" are about deepseek-1.3B, not scoring.

## 5. Figures

**Data**
- `figs/fig1_census.pdf`: I extracted every number from the PDF text layer. All 305 cells equal the serial
  15-task scores, row by row in the plotted column order. On the PNG, the seven red boxes sit on the seven suspects.
- `figs/fig2_calibration.pdf`: values unchanged (106/113/104/102, 13/25/30, 76/89/81/125, 80/86/77, 0/34/21/37).

**Size**
- Every text span in both PDFs is 8.0 pt: 217 spans in Fig. 1 and 44 in Fig. 2, all TimesNewRomanPSMT.
- Page widths are 514.07 bp (= 516 TeX pt = `\textwidth`) and 472.95 bp (= 0.92 `\textwidth`), so both print
  at scale 1.0, that is 8.0 bp ≈ 8.03 pt.
  - I confirmed the scale from main.pdf: the current figures print at 6.98 pt, so their 7 pt text was
    scaled by 0.9972 = 514.07/515.52.
  - The current figures therefore print below 8 pt; the new ones fix that.
- I viewed both PNGs: nothing overlaps or is clipped. The raised "current mix" bracket clears the "37" label,
  and "registry mix" stays below the dashed 74 line.

**Height**
- The new figures are taller: Fig. 1 226.1→234.7 bp and Fig. 2 169.2→182.2 bp.
- The right column of page 10 ends at y = 384 of about 720, so the 10-page limit is not at risk. Float
  placement can still move, so rebuild and look.

## 6. Problems and corrections

1. **Figure includes (PAPER_DIFF row 10 and the summary).** "Point the includes at `analysis/serial/figs/` or
   copy the files over": the first option breaks the release.
   - `build_release.sh` copies `figs/fig1_census.pdf` and `figs/fig2_calibration.pdf` into the arXiv folder and
     zips `figs/…`.
   - An arXiv `main.tex` that includes `analysis/serial/figs/…` would not compile there.
   - **Correction:** keep `\includegraphics{figs/…}` unchanged and copy `analysis/serial/figs/fig1_census.pdf`
     and `fig2_calibration.pdf` (and the PNGs) over `figs/`. This is a step for the author, since figs/ was
     off limits here. Then rebuild and check float placement.
2. **"Every result re-scored serially" (row 5, the paste-ready paragraph, row 21 text).** This overstates the
   method: 14,462 passes were carried over from the pool scorings.
   - Carrying them over is sound: load can only turn passes into time-outs, and 453 of 453 sampled passes held.
   - The text must still say what was done. **Correction:** the L255–261 paragraph in section 7.
3. **L672 "correcting it changed no verdict" (row 21 marked optional).** The pod correction changed no class
   (verified). The serial one changes two stage-two classes: mistral v0.2 q8_0 HEALTHY→DEGRADED and
   yi-coder 1.5B q2_K DEGRADED→HEALTHY. **Correction:** "changed no suspect or attribution verdict". Make it a
   required edit.
4. **SERIAL_REPORT.md documentation.** No effect on any verdict or number.
   - "1-minute load average at set boundaries: 1.80 to 3.17" is true at boundaries only. Per instance it ranged
     1.60–4.63, with 462 instances at ≥ 3.5, and this Mac idles at about 2.0. State the per-instance range.
   - The task goal "only the load effect changes" holds only for the sets first scored on this Mac. For the
     pod-scored sets the Python and tree-sitter versions and the ground-truth timings also changed. The Notes
     already say this; my checks in section 2 found no effect.
   - Mbpp/160 passes serially at 0.91 of its limit, which is fragile. It moves no printed number.

## 7. Final corrected list of main.tex edits

Line numbers refer to main.tex as it stands (md5 1a7d316a…).

| # | Line | Old | New |
|---|---|---|---|
| 1 | 210 | `\textbf{15-task screen}\\43 flagged\\(of 305)` | `\textbf{15-task screen}\\39 flagged\\(of 305)` |
| 2 | 217 | `Counts are for the official library with corrected scoring.` | `Counts are for the official library with serial scoring.` |
| 3 | 255–261 | the whole "A scoring fault, corrected." paragraph (below) | the paragraph below |
| 4 | 334 | `(corrected scores). All six low-baseline tags,` | `(serial scores). All six low-baseline tags,` |
| 5 | 352 | `\includegraphics[width=\textwidth]{figs/fig1_census.pdf}` | unchanged; copy `analysis/serial/figs/fig1_census.pdf` (and `fig2_calibration.pdf`) over `figs/` |
| 6 | 353 | `15-task suite score (of 15, corrected scoring)` | `15-task suite score (of 15, serial scoring)` |
| 7 | 495 | `(Table~\ref{tab:sizes}: 12--14 of 15)` | `(Table~\ref{tab:sizes}: 13--15 of 15)` |
| 8 | 518 | `\texttt{q2\_K} & 12 / 12 / 11 & 0 / 0 / 15 \\` | `\texttt{q2\_K} & 13 / 13 / 12 & 0 / 0 / 15 \\` |
| 9 | 519 | `\texttt{q3\_K\_S} & 14 / 14 / 13 & 0 / 0 / 2 \\` | `\texttt{q3\_K\_S} & 15 / 15 / 14 & 0 / 0 / 2 \\` |
| 10 | 520 | `\texttt{q3\_K\_M} & 14 / 14 / 14 & 0 / 0 / 9 \\` | `\texttt{q3\_K\_M} & 15 / 15 / 15 & 0 / 0 / 9 \\` |
| 11 | 521 | `\texttt{q3\_K\_L} & 14 / 14 / 13 & 0 / 0 / 7 \\` | `\texttt{q3\_K\_L} & 15 / 15 / 14 & 0 / 0 / 7 \\` |
| 12 | 606 | `On the corrected census scores, every subset of 5 or more of the 15 tasks` | `On the serial census scores, every subset of 3 or more of the 15 tasks` |
| 13 | 606 | `drops out of 32--87\% of subsets` | `drops out of 31--87\% of subsets` |
| 14 | 606 | `drops out of at most 25\%, only at 8 or fewer tasks` | `drops out of at most 22\%, only at 8 or fewer tasks` |
| 15 | 606 | `a mean Jaccard index of 0.61 at 5 tasks and 0.77 at 10` | `a mean Jaccard index of 0.63 at 5 tasks and 0.78 at 10` |
| 16 | 672 | `correcting it changed no verdict.` | `correcting it changed no suspect or attribution verdict.` |
| 17 (optional) | 317 | `Scoring & EvalPlus 0.3.1, HumanEval+ plus-tests \\` | `Scoring & EvalPlus 0.3.1, HumanEval+ plus-tests, one evaluation at a time \\` |

Edit 3, old (L255–261):

```
\emph{A scoring fault, corrected.} The census scorer marked HumanEval/15 as failed for every artifact,
although most generations contain the standard solution. Re-scoring all archived transcripts with the
same EvalPlus version passes it for 134 of the 305 official artifacts, and one further artifact gains a
different task (HumanEval/23); 135 artifacts gain one task and none loses one. The task's strengthened
tests are slow and can exceed the time limit when scoring runs in parallel, so the corrected scores are
lower bounds. The correction reduces stage-one flags from 50 to 43 and leaves every class count and all
seven suspects unchanged. We report corrected scores throughout.
```

Edit 3, new:

```
\emph{A scoring fault, corrected.} The census scorer marked HumanEval/15 as failed for every artifact,
although most generations contain the standard solution. The task's strengthened tests are slow and can
exceed the time limit when scoring runs in parallel, so we re-evaluated every failed task of every result
set serially, one evaluation at a time with the same EvalPlus version and its default time limits, together
with a 3\% sample of passes, none of which changed. HumanEval/15 then passes for 275 of the 305 official
artifacts, one of which also gains HumanEval/23; no task that passed before fails, and the task's slowest
test now uses at most 18\% of its time limit. The correction reduces stage-one flags from 50 to 39 and
leaves every class count and all seven suspects unchanged, although two non-suspect tags trade places
between healthy and degraded. We report the serial scores throughout.
```

Every number in the new paragraph is verified above:
- 275 of 305, and the HumanEval/23 artifact;
- 0 losses;
- 3% sample, 453 of 453 passes held;
- "at most 18%": slowest test at 0.089–0.179 of its limit over all 182 HumanEval/15 flips;
- 50 → 39;
- 271/3/6/7/18 with the two swaps.

The paragraph is about 25 words longer than the current one. Page 10 has room.
