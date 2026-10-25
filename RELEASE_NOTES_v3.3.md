# quantcheck v3.3

v3.3 keeps every result of v3.2.1 and every data file except the note in
`serial/tuning_configs.json`, and adds the per-task results of the 24
screen-tuning configurations, so that no value in the analysis outputs is
copied from a committed file any more. What still rests on the census
`serve.log` is read from its released extraction, as before, or marked in
`PROVENANCE.md`.

## Added

- `rerun-2026-10/serial/tuning_p1_humaneval_serial.jsonl` and
  `tuning_p1_mbpp_serial.jsonl`: the serially re-scored HumanEval+ (164 tasks)
  and MBPP+ (378 tasks) results of the 24 Qwen2.5-Coder configurations the
  screen was tuned on, one row per configuration with the per-task verdicts
  (`per_task`), `n_pass`, the pool-scored `old_n_pass`, the re-evaluated tasks
  and the tasks whose verdict changed (`flips`). The rows equal the author's
  working-copy files (sha256 `12a09d6e…` and `a1705020…`, the hashes recorded
  in `a1_serial.json`) with two provenance fields removed, the transcript path
  and a note on the pool-scored source; the released files hash to
  `9882a112…` and `f32d4430…`. The tuning study's original, pool-scored
  EvalPlus result files, which hold its generated solutions, remain unreleased.
  `serial/instances.jsonl` and `serial/flips.jsonl` cover the census and rerun
  sets only; the tuning sets' re-evaluations are summarized in
  `serial/serial_summary.json` and `serial/SERIAL_REPORT.md`.

## Changed

- `serial/numbers_regroup.py`, `serial/numbers_serial.py`, `serial/a1_regroup.py`
  and `gate/facts_b.py` recompute the tuning values from the released files by
  default: the 39-task pool and the suite, the known failure's 0 of 15 and 0 of
  164, the MBPP+ range of the healthy configurations (38.6–70.1%) and the
  known failure's 7 of 378, the "94% of random 15-of-164 suites" figure
  (0.943), and the summary of the tuning configurations' full runs. Every
  analysis value (counts, rates, figures) in the committed outputs is
  unchanged; their provenance fields change as follows:
  `a1_regroup.json` records the two tuning files under their names in
  `calibration_94pct_check.tuning_source` and `meta.inputs_sha256` (with the
  released files' hashes) and sets `p1_eval_files_sha256_unchanged` to a note
  that the original files were not checked; `facts_b.json` sets
  `fullrun_table.tuning_full164_separate_study.from_committed_file` to false
  and updates that block's `note`. No other output carries a
  `from_committed_file` key after a clean run.
- `a1_regroup.py` no longer needs the original EvalPlus result files
  (`QUANTCHECK_P1_RESULTS`): the serial-versus-pool differences are rebuilt
  from each row's `flips`, with the row's `old_n_pass` as the check. When the
  original files are present they are compared with the flips and with the
  hashes in `a1/a1_results.json`. If the tuning files are removed, the script
  falls back to the committed values and marks `calibration_94pct_check`
  `from_committed_file`, as `numbers_regroup.py`, `numbers_serial.py` and
  `facts_b.py` do for their blocks.
- `serial/a1_serial.py` (superseded by `a1_regroup.py`) stops with a message
  and writes nothing when the original EvalPlus result files are absent (in
  v3.2.1 it stopped with a `FileNotFoundError` for the then-unreleased serial
  file).
- `serial/tuning_configs.json`: the note no longer says the per-task results
  are unreleased (the ids are unchanged; the file's hash in
  `miss_audit/BOUNDS.md` is updated accordingly). `CITATION.cff`: version 3.3.
- README, PROVENANCE, `gate/FACTS_B.md` and `miss_audit/BOUNDS.md` describe
  the released files instead of withheld ones. The PROVENANCE row for the
  HumanEval/15 timing bound now states it over all 192 passing
  evaluations with a timing record (at most 20%, maximum 0.1966 in the
  `census_full164` set), as the paper does.
