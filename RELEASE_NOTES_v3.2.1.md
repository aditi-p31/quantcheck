# quantcheck v3.2.1

v3.2.1 changes documentation only. Every data file, script and result is
identical to v3.2.

## Corrected

- `README.md`: the description of `rerun-2026-10/RUN_PLAN.md` said that its log
  records each later addition and its expected reading before it ran. The log
  shows that most later additions were entered before they ran and that four
  carry a fixed expected reading; the positive control and the
  order-independent tensor comparison were logged with their results; the
  serial re-scoring (`rerun-2026-10/serial/SERIAL_REPORT.md`) and the
  miss-audit closure run (`rerun-2026-10/scripts/v1cases.sh`) are documented
  outside the plan. The README now says so.
- `README.md` and `PROVENANCE.md`: Qwen's own GGUF files are described by
  their metadata (`general.finetune` = `Instruct-AWQ`, no `quantize.imatrix`
  keys) rather than as "AWQ-derived", which inferred a production step that
  the metadata alone does not establish.
