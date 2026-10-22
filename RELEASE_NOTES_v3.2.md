# quantcheck v3.2

v3.2 keeps every data file and every result of v3.1. It adds two analyses
behind the paper "Broken on Arrival: Non-Functional Quantized LLM Artifacts in
Public Model Registries and How to Catch Them", and corrects how the release
describes the first-version miss-audit sample and the repetition statistic.

## Added

- `rerun-2026-10/miss_audit/bounds.py`, `bounds.csv`, `bounds.json`,
  `BOUNDS.md`: population bounds for the miss audit. Each bound is the largest
  number of non-functional census files (at most 16 of the 164 HumanEval+
  tasks) that the audit outcome does not reject at the 5% level, by exact
  test inversion over the ten family strata. The paper prints one row: for
  the 223 unflagged official tags outside the first-version sample, the 56
  seeded draws give a 95% bound of 22 non-functional census files (9.9%),
  counting the August file of the re-published `gemma3:4b-it-q8_0` as failed.
  The table in `BOUNDS.md` lists the other rows (15 to 30 tags) with the
  assumption each one needs. `bounds.py` also regenerates both seeded draws
  from their seeds.
- `rerun-2026-10/miss_audit/bounds_check.py`: rows 1 to 4 repeated in exact
  fractions by a depth-first search over all allocations.
- `rerun-2026-10/miss_audit/v1_seed_search.py`, `v1_seed_search.log`: a seed
  search over 48 frame variants and about 300,000 seeds that does not
  recover the first-version draw.
- `rerun-2026-10/gate/facts_b.py`, `facts_b.json`, `FACTS_B.md`: for each RQ3
  output-statistic rule, every flagged tag that is not a suspect and whether
  a full 164-task run puts it above or at most 16 of 164; the proposed
  acceptance gate applied to the census (of the 32 flagged non-suspect tags,
  8 published, 8 withheld, 16 without a full run); the persistence of the
  suspects' files; the repetition score; and every non-suspect official tag
  with a full 164-task run (16 above 16 of 164, 8 at or below).
- README sections "Miss-audit population bound" and "Flags, gate and full
  runs", the latter with the full-run table. The census full runs were chosen
  by the fixed rule in `harness/fullrun.py`, not at random, and the README
  says so.
- `PROVENANCE.md` rows for the population bound, the gate evaluation on the
  census, the output-statistic flags, the selection of the census full runs,
  and the repetition-score formula (`harness/audit.py` lines 40 to 51 and
  117).

## Corrections

- **First-version audit sample.** v3.1's `PROVENANCE.md` cited
  `sensitivity_sample.json` as evidence that the unflagged artifacts were
  "sampled at random". That file only lists which 10 tags were picked. How
  they were drawn is not recorded (no seed, script or frame), and the sample
  looks restricted to files of at most 3.9 GB. `PROVENANCE.md` now says so
  and cites the two seeded manifests (`rerun-2026-10/fn_sample_30.json`,
  `fn_sample_b.json`) as the evidence for the 56 October draws.
- **Repetition statistic.** The README called `rep6_share` a "repeated 6-gram
  share". It is six times the count of the most frequent word 6-gram divided
  by the word count, so it can exceed 1 (up to 5.348 for one census
  generation). The README now calls it a 6-gram repetition score and gives
  the formula. The field names in the data are unchanged.
- **Re-downloads.** `PROVENANCE.md` named two re-downloaded files as
  byte-identical to the census copies; all five re-downloaded suspect files
  (the four Qwen2.5-Coder-3B tags and phi3.5 q2_K) are, and the row now lists
  all five.
- **Output-statistic flags.** The release no longer calls the non-suspect
  tags that the RQ3 rules flag false positives: several of them solve at most
  16 of 164 in a full run. The field name `false_positives` in
  `numbers_regroup.json` is kept for compatibility, and the v3.0 reports
  `serial/PAPER_DIFF.md` and `serial/VERIFY_REPORT.md` are left as written.

## Reproduce

```
python3 rerun-2026-10/miss_audit/bounds.py
python3 rerun-2026-10/miss_audit/bounds_check.py
python3 rerun-2026-10/gate/facts_b.py
python3 rerun-2026-10/miss_audit/v1_seed_search.py > v1_seed_search.log   # about 16 minutes
```

All four use only the standard library and read only files in this release.
`bounds.py` and `facts_b.py` reproduce their committed outputs byte for byte,
and `v1_seed_search.py` reproduces its log except for the elapsed seconds.
Two inputs of `facts_b.py` are not released: the census Ollama server log
(the script reads its released extraction, `census_digests.json`, instead)
and the full-run results of the screen-tuning configurations, a separate
study. `facts_b.json` keeps only a summary of the latter (counts and range),
copied from the committed output and marked `from_committed_file`.

The v3.1 commands (`numbers_regroup.py`, `a1_regroup.py`,
`figures_serial.py`) and their outputs are unchanged.
