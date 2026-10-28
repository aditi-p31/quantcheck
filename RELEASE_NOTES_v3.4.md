# quantcheck v3.4

v3.4 keeps every result and data file of v3.3 and adds one experiment, with a
correction to the documentation of the census template setup for Hugging Face
community files. No census score, class, suspect, miss-audit value or attribution
verdict of the seven suspects changes; the community pair's verdict changes
from backend-dependent to template-dependent.

## What was wrong

v3.3's `PROVENANCE.md` stated that HF files ran with the chat template of the
matching official tag, citing `template_donor` in `results/audit_results.jsonl`.
That field is null on all 22 completed community rows: `harness/hf_audit.py`
copies a template only for the families in its `TEMPLATE_DONOR` table, and the
community entries carry the family `mixed`. The 22 community files therefore
ran with no `TEMPLATE` line, and Ollama used each file's own chat template,
or llama-server's default ChatML format where the file has none. The
statement holds for the seven `hf-adjudication` referee files of the census
(donor tags of the same family; see `PROVENANCE.md`) and for every HF file of
the October reruns before the template test (`donor` in
`rerun-2026-10/results*/runs.jsonl`).

The two TheBloke deepseek-coder-6.7B files carry no `tokenizer.chat_template`.
For them Ollama selects no template (`ollama show --template` prints
`{{ .Prompt }}`), and its bundled llama-server formats each request with its
default ChatML template, which the model was not trained on (server log:
`template selection ... selected=none`, `chat format: peg-native`, prompts 16
tokens longer than under the instruction template). The Metal
replication (`harness/mac_night.py`) supplied the deepseek-coder instruction
template. The paper's arXiv v2 text compared the census (5 and 6 of 15 on
CUDA) with Metal (13 and 15) "under the same runtime release and template"
and called the pair backend-dependent. The runtime release was the same; the
template was not.

## Added

- `rerun-2026-10/results-tpl/`: the template test of 28 October 2026 on a
  fourth RTX 4090 pod with Ollama 0.32.6 from the October pods' archive
  (dec2fa50; same bundled llama.cpp build as the census, 96278e39f). Both files, checked against the census digests, ran under three
  Modelfiles on the 15 screen tasks and all 164 HumanEval+ tasks: no template
  (the census condition), the instruction template of the Metal runs, and the
  `deepseek-coder:6.7b-instruct-q4_K_M` Modelfile as `run_entries.donor_modelfile`
  copies it. Serial scores (one EvalPlus worker, as for every other set):

  | File | No template | Instruction template | Donor Modelfile (see note) |
  |---|---|---|---|
  | Q3_K_M, 15 screen tasks | 5 | 13 | 12 |
  | Q3_K_M, all 164 | 16 | 98 | 79 |
  | Q4_K_M, 15 screen tasks | 6 | 15 | 14 |
  | Q4_K_M, all 164 | 18 | 101 | 93 |

  With no template the pod reproduces the census screen answers byte for byte
  on all 30 (one census answer carries the v3 email redaction, now applied to
  the new transcript too), and 87% and 96% of the 164-task generations hit the
  token cap. The census ran no 164-task run of these files; the earlier
  no-template run in `results-native/` solved 22 and 16, with truncation 0.872
  and 0.939 (the arXiv v2 text's 87% and 94%). With the instruction
  template the CUDA scores equal the Metal scores. The pair works on both
  backends with the template and fails on CUDA without it (Metal was not run
  without one).
- `rerun-2026-10/serial/tpl_serial.jsonl`: the serial scores in the release's
  record shape; `rerun-2026-10/scripts/tpl_test.sh`, `run_template_test.py`,
  `tpl_entries.json` (the pod scripts) and `score_template_serial.py` (the
  serial scorer).
- `serial/numbers_regroup.py` gains a `template_test` block in
  `numbers_regroup.json` with the values above, the adopted templates, the
  invented-chat-turn counts and the check that the files equal the census
  digests. Every other key of `numbers_regroup.json` is unchanged, except that
  `_meta.added_keys` now also names `template_test`.

## Changed

- `PROVENANCE.md`: the template row is corrected (above) and a section
  "Template test (v3.4)" is added.
- `README.md`: a finding on the pair; the `results-native/` row now says those
  runs repeated the census condition (no `TEMPLATE` line); rows for
  `results-tpl/` and the new scripts; file-table, pod and rescoring notes for
  `tpl_serial.jsonl` and `results-tpl/`; the redaction note.
- `rerun-2026-10/ds13/ds13_outputs.py`: docstring note that its
  `empty template` label for the TheBloke 6.7B census group means no `TEMPLATE`
  line (llama-server's default ChatML format); the key in
  `outputs_summary.json` is unchanged.
- `disclosure/DISCLOSURES.md` (commit 258ae99, after v3.3): links the
  27 October 2026 follow-up comment on ollama/ollama#18252 that withdraws the
  defect claim, and describes Qwen's GGUF files by their metadata label.
- `harness/deepseek_native.py` and `harness/mac_night.py`: docstring notes on
  what each run did and did not vary.
- `rerun-2026-10/scripts/run_entries.py`: docstring note that
  `donor_modelfile()` drops lines beginning with `#` from a double-quoted
  TEMPLATE (deepseek-coder's `### Instruction:` and `### Response:`). The
  function is unchanged; no October rerun before the template test used such
  a donor.
- `serial/a1_regroup.json`: only its recorded SHA-256 of `numbers_regroup.json`
  changes (that file gained the `template_test` key); every value is unchanged.
- `disclosure/DISCLOSURES.md`: the pair is described as template-dependent.
- `harness/hf_audit.py`: docstring note that community entries get no
  `TEMPLATE` line.
- `rerun-2026-10/gate/FACTS_B.md`: the recorded hash of `numbers_regroup.json`.
- `rerun-2026-10/scripts/tpl_test.sh` (added above) differs from the first
  launch's copy: the released script sets
  `OLLAMA_HOST=http://127.0.0.1:11434`; the first launch exported the host
  without the scheme, every generation call failed, and the runner was
  relaunched by hand with the scheme on the same server (recorded in
  `results-tpl/tpl.log` and `aborted_first_attempt/`).
- Seven distinct email addresses that the model reproduced in three new
  transcripts (11 occurrences in eight answers) are replaced by
  `<EMAIL_REDACTED>`, as in v3; scores recomputed, unchanged.
- `CITATION.cff`: version 3.4.

## Note on the donor condition

Because of the `#`-line behaviour above, the donor condition tested the
deepseek-coder system prompt without instruction markers (Ollama adopted
`{{ .System }}\n{{ .Prompt }}\n`). It also removes the failure. The condition
the paper reports is the instruction template. None of the earlier October
reruns used a donor with such lines (Qwen2.5-Coder and phi3.5 only).
