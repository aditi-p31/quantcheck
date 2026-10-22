# Miss audit (RQ4): population bounds and the assumptions behind them

Built 22 Oct 2026 by `bounds.py` (Python stdlib, read-only on every input). Per-row results are in
`bounds.csv`, and `bounds.json` adds the frame, strata, outcome checks and diagnostics. Every number
below comes from those files. All inputs are in this release (section 7).

```
python3 rerun-2026-10/miss_audit/bounds.py          # rewrites bounds.csv and bounds.json (a few seconds)
python3 rerun-2026-10/miss_audit/bounds_check.py    # exact-fraction check of rows 1 to 4
python3 rerun-2026-10/miss_audit/v1_seed_search.py  # seed search for the first-version draw (about 16 minutes)
```

`bounds.py` reproduces the committed `bounds.csv` and `bounds.json` byte for byte. `v1_seed_search.py`
reproduces `v1_seed_search.log` except for the elapsed seconds on its `done` lines.

**Event.** A tag's August census file is non-functional: it solves at most 16 of the 164 HumanEval+
tasks under the census settings (temperature 0, seed 42, 768 new tokens, context 2,048).

**Population.** The 233 official Ollama tags that passed the screen on the original 15-task scores
(at least 9 of 15) and are not among the 23 screen-tuning configurations in the census, each as served
at the August 2026 census. Some rows use the 223 of them not in the first-version sample.

## 1. How the 10 first-version tags were drawn: what is recorded

**Recorded**

- `sensitivity_sample.json` (sha256 `4a43d0aa00c9e95c...`) lists the 10 tags with quant, size in
  parameters, file size, URL, family and channel. In the author's working copy its modification time
  is 12 Aug 2026 20:39:18 PDT (13 Aug 03:39:18 UTC), the same second as `heldout_49.json`, and
  `harness/audit.py` was saved a minute later (git does not keep file times).
- `results-sensitivity/audit_results.jsonl` gives each run's start and end time (13 Aug, 05:24 to
  05:40 UTC) and pull time. It has no sampling fields.
- The first-version paper (arXiv:2609.05881v1) calls the sample "a random sample of unflagged
  artifacts" and "a stratified random sample of ten unflagged artifacts". It gives no strata, frame,
  seed or allocation rule.
- Up to v3.1, `PROVENANCE.md` and `README.md` pointed to `sensitivity_sample.json` as the
  first-version sample without saying how it was drawn; `PROVENANCE.md` cited it under "sampled at
  random". v3.2 corrects both.

**Not recorded anywhere searched**

- No seed, script, frame definition, frame size or allocation rule. The project's `harness/` (7
  scripts) and `analysis/` (4 scripts) contain no sampling code. The only seed in them is the
  decoding seed 42. The project's design notes, run books and memos (not released) say nothing on
  the draw, and `rerun-2026-10/RUN_PLAN.md` mentions only "v1's 10".
- The session logs of the coding assistants used on the working machine have no entry between 03:34
  and 04:00 UTC on 13 Aug. None of them contains a command that writes `sensitivity_sample.json` or
  `heldout_49.json`.
- A seed search (`v1_seed_search.py`, log in `v1_seed_search.log`) does not recover the draw. It tried
  `random.Random(s).sample(pool, 10)` and shuffle-then-take-10 for seeds 0 to 300,000, 20260801 to
  20260831 and eight common seeds, over 48 frame variants: 233 or 255 tags; no file-size cut or a cut at
  4.0, 4.5 or 5.0 GB; with or without qwen2.5-coder; three orderings. None reproduces the 10 tags,
  either in order or as a set. A plain search like this does recover both October draws (below).

**What the sample itself shows** (a diagnostic, not a pre-planned test)

- Allocation across the ten strata: codellama 0, deepseek 1, gemma 1, granite 3, llama 2,
  mistral 1, phi 1, qwen2.5-coder 0, starcoder2 0, yi-coder and codegemma 1.
- All 10 files are between 0.904 and 3.9 GB, and none is above 7B parameters. In the 233-tag frame,
  110 tags have files larger than 3.9 GB. If the 10 had been drawn at random within strata with this
  allocation, the chance that all 10 would be 3.9 GB or smaller is 0.0028; for a simple random 10 of
  the 233 it is 0.0014. The cut-off was read off the sample, so this probability is only indicative.
  Still, the draw looks restricted to small files, which would fit the 16 GB Mac where the first
  attempt ran.
- So rows 1 and 2 below depend on an assumption that is not only unrecorded but hard to square with
  the sample.

**The two October rounds, by contrast, are fully recorded and reproduce exactly.**
`rerun-2026-10/fn_sample_30.json` (seed 20261021, frame 223, 3 per family group) and
`rerun-2026-10/fn_sample_b.json` (seed 20261022, frame 194) are the manifests written before the runs.
`bounds.py` regenerates both lists, in order, with `random.Random(seed)`, taking the family groups
in sorted order and calling `rng.sample(sorted(group tags), min(3, group size))`. The frame is the
233 minus the first-version 10 (and, for round two, minus round one). This shows that the
within-stratum design of the 56 draws is real (`bounds.json`, `seeded_draws_reproduced`).

## 2. Frame and strata

Rebuilt from `results/audit_scored.jsonl` (305 official tags; 255 at 9 or more of 15; minus 22
unflagged tuning configurations named in `rerun-2026-10/serial/tuning_configs.json` = 233). The two
October frames are 223 and 194, matching the manifests.

| Stratum | Frame (233) | First-version draws | All draws (66) | Frame without first version (223) | Seeded draws (56) |
|---|---:|---:|---:|---:|---:|
| codellama | 18 | 0 | 6 | 18 | 6 |
| deepseek-coder, deepseek-coder-v2 | 12 | 1 | 7 | 11 | 6 |
| gemma2, gemma3 | 22 | 1 | 7 | 21 | 6 |
| granite-code, granite3.1-dense | 57 | 3 | 9 | 54 | 6 |
| llama3.2, llama3.1 | 25 | 2 | 8 | 23 | 6 |
| mistral, codestral | 22 | 1 | 7 | 21 | 6 |
| phi3.5, phi4 | 10 | 1 | 7 | 9 | 6 |
| qwen2.5-coder | 24 | 0 | 6 | 24 | 6 |
| starcoder2 | 2 | 0 | 2 | 2 | 2 |
| yi-coder, codegemma | 41 | 1 | 7 | 40 | 6 |
| **Total** | **233** | **10** | **66** | **223** | **56** |

## 3. Outcomes the bounds use (checked against the raw records)

- All 66 audited tags solve 8 to 41 of the 49 held-out tasks (serial scores), so none solves 2 or
  fewer.
- 55 of the 56 October runs loaded the census digest (`runs.jsonl` blob compared with
  `census_digests.json`). The exception is `gemma3:4b-it-q8_0`. Its census file is `b3ec67796e03...`
  and its October file `b46dd6d60d63...`. The October file solves 34 of 49. The August file has only
  its screen record: 15 of 15 on serial scoring (14 on the original scorer), below the 17 a
  certificate needs.
- The two first-version tags without a certificate in the original audit were rerun on all 164 tasks
  on their census digests: `granite-code:3b-instruct-q3_K_M` solves 65 and `mistral:7b-instruct-q3_K_S`
  solves 44. The other 8 first-version tags each solve 19 to 29 of 49 in a run whose file digest and
  backend were not recorded.

## 4. Sensitivity table

Each bound is the largest total D = sum of D_h for which the probability of the observed outcome is
at least 0.05. That probability is the product over strata of hypergeometric terms: P(X_h = 0 | D_h)
for zero failures among n_h draws from N_h, and P(X_h <= 1 | D_h) for the gemma stratum when its August
file counts as failed. The method needs simple random sampling without replacement within each
stratum and nothing else. It does not assume that related tags of one checkpoint fail independently.
Two sequential rounds within a stratum combine into one simple random sample of their total size, so
the 56 draws are 6 per stratum (2 for starcoder2) from the 223. `bounds_check.py` repeats rows 1 to 4
with a depth-first search over all allocations in exact fractions and gets the same counts.

| Row | Population | Draws treated as random | Gemma August file | First-version 10 | 95% upper count | Share |
|---|---|---|---|---|---:|---:|
| 1 | 233 | all 66 | October file stands in (passed) | random within strata; 8 audit runs taken as census files | **15 / 233** | 6.4% |
| 2 | 233 | all 66 | counted as failed | as row 1 | **17 / 233** | 7.3% |
| 3 | 223 (233 minus first-version 10) | 56 seeded | October file stands in (passed) | outside the population | **20 / 223** | 9.0% |
| 4 | 223 | 56 seeded | counted as failed | outside the population | **22 / 223** | 9.9% |
| 5 | 233 | 56 seeded | counted as failed | no assumption: the 8 without a file record count as failures, the 2 full reruns as passes | **30 / 233** | 12.9% |
| 4b | 233 | 56 seeded | counted as failed | taken as observed passes (8 audit runs taken as census files), not as random draws | 22 / 233 | 9.4% |

The paper prints row 4. Rows 1 to 5 equal the values of an independent review of the paper draft
(the `review_value` and `matches_review` columns of `bounds.csv`); row 4b is supplementary.

Worst-case allocations at the bound, with the non-rejection probability at the bound and the largest
probability at the bound plus one:

| Row | Allocation at the bound | P at bound | Max P at bound + 1 |
|---|---|---:|---:|
| 1 | granite 10, yi/codegemma 5 | 0.0562 | 0.0455 |
| 2 | gemma 3, granite 10, yi/codegemma 4 | 0.0536 | 0.0435 |
| 3 | granite 17, yi/codegemma 3 | 0.0545 | 0.0457 |
| 4, 4b, 5 (stratified part) | gemma 3, granite 16, yi/codegemma 3 | 0.0528 | 0.0445 |

Allocations at the bound are not unique; the bound is. The worst case always puts most failures in
granite, the largest stratum with the lowest sampling rate.

For reference, two summaries with stronger assumptions: the Wilson 95% upper limit for 0 of 66, which
treats the 66 as independent draws with one shared rate, is 5.50% (6.42% for 0 of 56). A single
hypergeometric bound that treats the 66 as one simple random sample of the 233 is 8 tags (3.4%).
Neither fits the stratified design, and both include the first-version 10.

## 5. The row the paper prints

The paper (RQ4, "Population") bounds only the 223 tags outside the first-version sample, because the
first-version draw is unrecorded, and reports **row 4**: an exact stratified 95% bound of 22
non-functional census files (9.9%), counting the re-published tag's August file as failed. The other
rows, tighter but resting on further assumptions, are the ones it leaves to this table. Row 4 names the
population (the 223 tags outside the first-version sample, as census files), the event
(non-functional), and the assumptions (the seeded draws are random within strata, and the re-published
tag's August file counts as failed).

Why row 4:

1. Its only sampling assumption is recorded and checked. The seeds, frames and lists are in the
   manifests, and both draws regenerate exactly from the seeds.
2. It does not use the first-version draw, whose procedure is unrecorded and whose file sizes do not
   fit the design that rows 1 and 2 assume.
3. It does not count the October `gemma3:4b-it-q8_0` file as the August one (its certificate covers
   the October file only). This costs 2 tags against row 3.
4. It does not need the first-version 10. The paper reports all 66, those 10 included, as above the
   threshold, as an observation rather than a population bound.

Not row 5: it would count 8 tags as possible failures even though each solved 19 or more held-out
tasks, only because their run's digest was not recorded, and it mixes a worst-case count with a
probability bound. It is kept here as the floor that needs no assumption about the first version.
Row 4b (22 of 233, 9.4%) keeps 233 as the denominator, but it brings back the identity assumption
for the 8 first-version runs.

## 6. Where the sampling evidence is

- First-version sample: `sensitivity_sample.json` (which tags were picked; not how).
- Seeded rounds: `rerun-2026-10/fn_sample_30.json` and `rerun-2026-10/fn_sample_b.json` (seed, frame
  size, per-family count, tag list), regenerated by `bounds.py`.
- Per-artifact audit evidence: `certificates.csv` and `certificates.json` in this folder.

## 7. Inputs (sha256, first 16 hex digits)

| File | sha256 |
|---|---|
| `results/audit_scored.jsonl` | `1175eea1d425c406` |
| `inventory_candidates.json` | `ac0769c6259da8ec` |
| `sensitivity_sample.json` | `4a43d0aa00c9e95c` |
| `rerun-2026-10/serial/tuning_configs.json` | `684f7041a2f4596b` |
| `rerun-2026-10/serial/sensitivity_serial.jsonl` | `406d9f130b791190` |
| `rerun-2026-10/serial/rerun_r3_serial.jsonl` | `8679891dbef66f93` |
| `rerun-2026-10/serial/rerun_r3b_serial.jsonl` | `41f57ec4dcade068` |
| `rerun-2026-10/serial/census_smoke_serial.jsonl` | `0b7815b651aa96a7` |
| `rerun-2026-10/fn_sample_30.json` | `3f16ae94754090ed` |
| `rerun-2026-10/fn_sample_b.json` | `ddf1fc4b4bb9be15` |
| `rerun-2026-10/results-v1cases/scored_serial.jsonl` | `aa5855faedb06171` |
| `rerun-2026-10/results-r3/runs.jsonl` | `34df4bc3ffb41fc2` |
| `rerun-2026-10/results-r3b/runs.jsonl` | `62cbf1986bc782bc` |
| `rerun-2026-10/serial/census_digests.json` | `210dfbe1fc7a627f` |

The bounds were first computed in the author's working copy, where the tuning-set names came from the
screen-tuning result file (not released) instead of `tuning_configs.json`; the 24 names are the same,
and the release copy of `bounds.py` reproduces those first outputs except for the input paths
recorded in `bounds.json` (`inputs`) and the `note` column: row 1 drops an outdated note, and row 4
now reads "the bound the paper prints".
