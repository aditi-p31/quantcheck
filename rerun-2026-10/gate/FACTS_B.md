# Output-statistic flags, the proposed gate on the census, persistence, repetition score, full runs

Recomputed from raw records by `facts_b.py` (stdlib, read-only on inputs); every number below is in `facts_b.json`.

```
python3 rerun-2026-10/gate/facts_b.py      # rewrites rerun-2026-10/gate/facts_b.json (under a second)
```

From a clean checkout it reproduces the committed `facts_b.json` byte for byte. Two inputs are not released:

- The census Ollama `serve.log`. The script takes each census tag's file digest from its released extraction,
  `rerun-2026-10/serial/census_digests.json`. With `QUANTCHECK_CENSUS_SERVELOG` pointing at the log it also parses
  the log itself and asserts that both agree (they do, for all 305 official tags).
- The full 164-task results of the 24 screen-tuning configurations, which belong to a separate study. They feed
  only `fullrun_table.tuning_full164_separate_study`, a summary (counts and range, no per-configuration values).
  Without them that block is copied from the committed `facts_b.json` and marked `"from_committed_file": true`;
  with `QUANTCHECK_TUNING_DIR` pointing at them it is recomputed.

Input hashes (sha256, first 8 hex digits): `rerun-2026-10/serial/census_smoke_serial.jsonl` `0b7815b6`,
`census_full164_serial.jsonl` `3b62186c`, `results/audit_results.jsonl` `02675274`, `results/audit_scored.jsonl`
`1175eea1`, `results/fullrun_scores.jsonl` `b66f1a39`, `rerun-2026-10/serial/census_digests.json` `210dfbe1`,
`rerun-2026-10/serial/numbers_regroup.json` `c01a88c7`. The script was first run in the author's working copy, on
the same records plus the two unreleased inputs; the release copy reproduces that output except for the tuning
summary block, which the first run listed per configuration.

Independent checks that pass (asserted in the script): output statistics recomputed from the 15 per-generation
metrics equal the stored `trunc_frac` / `rep6_share_mean` for all 305 official tags; serial scores equal the sum of
per-task booleans; an independent checkpoint grouping reproduces 35 groups and 271 healthy / 2 degraded / 6 low
baseline / 7 suspect / 19 no baseline, identical tag by tag to `numbers_regroup.json`; the RQ3 counts equal
`numbers_regroup.json` `rq3_output_rules`; fullrun_scores old values equal the `old_n_pass` in
census_full164_serial for all 27 rows; with the census log, a parse of it gives exactly one load per official run
window and equals `census_digests.json` for all 305 tags.

## 1. RQ3 output-statistic rules: every flagged non-suspect tag

Full = serial score on all 164 tasks (census pod, census file); old pod score in brackets where it differs.

| Rule | Tag | Class | 15-task | Full /164 | Status |
|---|---|---|---:|---:|---|
| trunc >= 0.2 (3/7 caught, 10 others) | deepseek-coder-v2:16b-lite q2_K | no baseline | 7 | 25 [24] | above 16 |
| | deepseek-coder:1.3b fp16 | low baseline | 2 | 16 | at most 16 |
| | deepseek-coder:1.3b q2_K | low baseline | 2 | 2 | at most 16 |
| | deepseek-coder:1.3b q3_K_L | low baseline | 1 | 10 | at most 16 |
| | deepseek-coder:1.3b q3_K_M | low baseline | 1 | 5 | at most 16 |
| | deepseek-coder:1.3b q4_K_M | low baseline | 1 | 7 | at most 16 |
| | deepseek-coder:1.3b q5_K_S | healthy | 4 | none | no full run |
| | deepseek-coder:1.3b q8_0 | healthy | 4 | none | no full run |
| | starcoder2:15b q2_K | no baseline | 9 | 65 [64] | above 16 |
| | starcoder2:15b q3_K_S | no baseline | 11 | none | no full run |
| rep6 >= 0.2 (3/7 caught, 4 others) | codellama:13b q4_0 | no baseline | 12 | none | no full run |
| | deepseek-coder-v2:16b-lite q2_K | no baseline | 7 | 25 | above 16 |
| | granite-code:3b-128k q2_K | healthy | 13 | none | no full run |
| | granite-code:3b-128k q3_K_M | healthy | 14 | none | no full run |
| either >= 0.3 (4/7 caught, 6 others) | deepseek-coder-v2:16b-lite q2_K | no baseline | 7 | 25 | above 16 |
| | deepseek-coder:1.3b fp16 | low baseline | 2 | 16 | at most 16 |
| | deepseek-coder:1.3b q2_K | low baseline | 2 | 2 | at most 16 |
| | deepseek-coder:1.3b q3_K_L | low baseline | 1 | 10 | at most 16 |
| | deepseek-coder:1.3b q4_K_M | low baseline | 1 | 7 | at most 16 |
| | starcoder2:15b q3_K_S | no baseline | 11 | none | no full run |

Status counts: trunc 5 at most 16 / 2 above / 3 no run; rep6 0 / 1 / 3; either-0.3 4 / 1 / 1.
So the extra flags are not all false positives: at the 0.3 rule four of the six are deepseek-coder-1.3B tags at
q2_K 2, q4_K_M 7, q3_K_L 10, fp16 16 of 164; the other two are deepseek-coder-v2 q2_K (25/164) and starcoder2
q3_K_S (no full run). Of the truncation rule's ten extra flags, five are verified at most 16 of 164. The paper
(RQ3) reports these counts and calls none of them false positives; v3.1 and earlier outputs
(`numbers_regroup.json` `rq3_output_rules`) keep the field name `false_positives` for the same counts.

## 2. The acceptance gate on the census

- Stage one (at least 9 of 15): **266 of 305 pass, 39 flagged** (original scorer: 50; 11 tags left the flag set,
  all moving from 8 to 9; none joined). Unflagged 266 = 248 healthy + 18 no baseline.
- The 39 flagged by class: **7 suspect, 6 low baseline, 2 degraded, 23 healthy-but-flagged, 1 no baseline**.
  The 23 flagged healthy tags score below 9 yet at least 60% of their group baseline (deepseek-coder-1.3B 4,
  gemma3:270m 5, mistral v0.2 6.5, gemma3:1b 8, llama3.2:1b 11, gemma2:2b 11, mistral:7b 10.5).
- 32 flagged non-suspects: **8 verified above 16/164, 8 verified at most 16/164, 16 with no full run**.
  By class: degraded 2 above; low baseline 6 at most 16; no baseline 1 above; healthy 5 above, 2 at most 16
  (deepseek-coder-1.3B q3_K_S 7/164, gemma3:270m q8_0 16/164), 16 no run.

Per flagged non-suspect group (flagged / with full run: results):

| Group (baseline) | Flagged | Full runs |
|---|---:|---|
| deepseek-coder:1.3b (4) | 12 | 7: q2_K 2, q3_K_S 7, q3_K_M 5, q3_K_L 10, q4_0 10, q4_K_M 7, fp16 16; none for q4_K_S, q5_K_S, q5_K_M, q6_K, q8_0 |
| deepseek-coder-v2:16b-lite (none) | 1 | q2_K 25 |
| gemma2:2b (11) | 1 | q2_K 25 |
| gemma3:1b (8) | 3 | q4_K_M 37; none for q8_0, fp16 |
| gemma3:270m (5) | 2 | q8_0 16, fp16 20 |
| granite3.1-dense:2b (14) | 1 | q2_K 17 |
| llama3.2:1b (11) | 4 | q3_K_M 42; none for q3_K_L, q4_0, q4_K_S |
| llama3.2:3b (15) | 1 | q2_K 30 |
| mistral:7b-instruct (10.5) | 1 | none (q3_K_L) |
| mistral:7b-instruct-v0.2 (6.5) | 6 | q3_K_L 44; none for q4_K_S, q5_K_S, q5_K_M, q6_K, q8_0 |

**Routing rule (the paper's proposed gate, "Confirm"):** *A flagged tag that is not a suspect, whatever its class,
goes to a full 164-task run on the same file and backend and is published only if it solves at least 17 tasks (the
run can stop once 17 distinct tasks pass); otherwise it is withheld.* (`gate.routing_rule_text`)

On the census it routes 32 tags: **publish 8** (deepseek-coder-v2 q2_K 25, gemma2:2b q2_K 25, gemma3:1b q4_K_M 37,
gemma3:270m fp16 20, granite3.1-dense:2b q2_K 17, llama3.2:1b q3_K_M 42, llama3.2:3b q2_K 30, mistral v0.2 q3_K_L 44),
**withhold 8** (seven deepseek-coder-1.3B tags at 2 to 16 including fp16, and gemma3:270m q8_0 at 16), **16 pending**
(no full run exists). The narrower rule "only no-baseline or low-baseline flags go to a full run" routes 7 (6 withhold,
1 publish) and would publish by class two tags already verified at most 16/164 (deepseek-coder-1.3B q3_K_S 7,
gemma3:270m q8_0 16), so routing by the flag, not the class, is the one that holds on existing evidence.

Calibrated builds against "publish if it clears the screen" (at least 9/15), with full scores:
Qwen Q2_K clears with all three (15/15; 106, 113, 104). Q3_K_M clears with own WikiText 9 (76) and bartowski 10 (81),
not own code 8 (89). Q3_K_L clears only with bartowski 9 (77); own builds at 7 and 8 fail the screen but solve 80 and 86.
phi3.5 Q2_K clears only with own WikiText 9 (37); bartowski 7 (34) fails. Q3_K_S clears with none (2, 4, 4; 13, 25, 30).
AWQ q2_k 14 (102) and q3_k_m 15 (125) clear. Under the routing rule the four calibrated builds at 7 to 8 of 15 would go
to a full run and be published (80, 86, 89, 34); Q3_K_S code and bartowski builds would also pass the 10% bar
(25, 30), since the bar targets non-functionality, not quality.

## 3. Persistence of the seven suspects

Census digest = blob loaded in the tag's census run window (`census_digests.json`, extracted from the census
serve.log). October = `rerun-2026-10/results*/runs.jsonl` blob name and, in `results/`, the computed file SHA-256;
the October `logs/serve.log` in `rerun-2026-10/logs.tar.xz` also shows 7 loads of each blob.

| Suspect | Census digest | October runs (pulls) | Equal |
|---|---|---|---|
| qwen2.5-coder:3b q2_K | 14c4247b… | 7 (1) | yes, blob and file hash |
| qwen2.5-coder:3b q3_K_S | 81d167af… | 7 (1) | yes, blob and file hash |
| qwen2.5-coder:3b q3_K_M | 9bb5d28b… | 7 (1) | yes, blob and file hash |
| qwen2.5-coder:3b q3_K_L | 7a88dc11… | 7 (1) | yes, blob and file hash |
| phi3.5:3.8b q2_K | 54d47caa… | 7 (1) | yes, blob and file hash |
| llama3.2:1b q2_K | d1ede02a… | 0 | not re-downloaded |
| llama3.2:1b q3_K_S | 81881dcc… | 0 | not re-downloaded |

Each of the five was pulled once in October (`results/`, base setting) and reused by the six R2 settings.
All four Qwen files and the phi3.5 file re-downloaded in October are byte-identical to the census copies (v3.1's
`PROVENANCE.md` named only Qwen q2_K and q3_K_M). Across all 70 official tags run in October, 69 equal their census
digest; the exception is gemma3:4b-it-q8_0.

## 4. Repetition score (`rep6_share`; `harness/audit.py` lines 40 to 51, artifact mean at line 117)

`toks = out.split()` (whitespace words, not model tokens); if `len(toks) >= 12`:
`rep6_share = round(6 * top / max(1, len(toks)), 3)` where `top` is the count of the most frequent overlapping word
6-gram; else 0.0. The artifact statistic is `rep6_share_mean`, the mean over the 15 generations.
Despite its field name it is not a bounded share: overlapping 6-grams count each repeated word up to six times, so a
one-word loop gives 6(n-5)/n (below 6) and a p-word loop about 6/p. **It exceeds 1.** Census (305 official tags,
4,575 generations): max per generation **5.348** (qwen2.5-coder:3b q3_K_S, HumanEval/107, 46 words, a one-word loop);
23 generations above 1 in 4 tags (qwen 3b q2_K 15, q3_K_S 4, phi3.5 q2_K 3, deepseek-coder-v2 q2_K 1); max artifact
mean **2.049** (qwen 3b q2_K), and q3_K_S 1.384 is the only other mean above 1. Healthy median mean 0.07. The RQ3
thresholds (0.2, 0.3) apply to the mean. The paper calls it a 6-gram repetition score (six times the count of the
most frequent word 6-gram over the word count) and notes that it can exceed 1.

## 5. Non-suspect official tags with a full 164-task evaluation

Census archive (27 runs; selection per `harness/fullrun.py`: every tag at original 15-task score at most 2 (13) plus
the lowest-scoring tag at 3 to 8 per model-size key (14); rule-based, not random). 20 are non-suspects:

| Tag | Class | 15-task serial (orig) | Full /164 |
|---|---|---|---:|
| starcoder2:15b q2_K | no baseline | 9 (8) | 65 |
| yi-coder:1.5b q2_K | healthy | 9 (8) | 48 |
| granite-code:20b q2_K | no baseline | 9 (8) | 46 |
| mistral:7b-v0.2 q3_K_L | healthy | 7 | 44 |
| llama3.2:1b q3_K_M | healthy | 8 | 42 |
| phi3.5:3.8b q3_K_S | healthy | 9 (8) | 42 |
| gemma3:1b q4_K_M | healthy | 7 | 37 |
| llama3.2:3b q2_K | degraded | 7 | 30 |
| deepseek-coder-v2:16b q2_K | no baseline | 7 | 25 |
| gemma2:2b q2_K | healthy | 7 | 25 |
| gemma3:270m fp16 | healthy | 5 | 20 |
| granite3.1-dense:2b q2_K | degraded | 5 | 17 |
| gemma3:270m q8_0 | healthy | 5 | 16 |
| deepseek-coder:1.3b fp16 / q3_K_L / q4_0 / q4_K_M / q3_K_S / q3_K_M / q2_K | low baseline (q3_K_S healthy) | 1 to 3 | 16 / 10 / 10 / 7 / 7 / 5 / 2 |

Of these 20, 12 solve more than 16 (17 to 65) and 8 at most 16 (seven deepseek-coder-1.3B, gemma3:270m q8_0).
Of the 11 tags unflagged by the serial rescoring, 4 have full runs: granite-code:20b q2_K 46,
phi3.5 q3_K_S 42, starcoder2 q2_K 65, yi-coder:1.5b q2_K 48.
Other full runs of non-suspect official tags on the census file (October): granite-code:3b q3_K_M 65 and
mistral:7b q3_K_S 44 (miss-audit closure), qwen2.5-coder:3b q4_K_M 132 (R6) and phi3.5 q4_K_M 74 (P0c); so 16
non-suspect tags have census-file full runs above 16. Separately, the 24 screen-tuning configurations of a separate
study include 22 census non-suspect Qwen tags with full runs (74 to 139 of 164); their file identity with the census
is not recorded and their results are not released, so they are left out of this table and of any artifact-table
claim (summary only, `fullrun_table.tuning_full164_separate_study`).
