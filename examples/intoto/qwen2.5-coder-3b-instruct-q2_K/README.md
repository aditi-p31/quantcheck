# in-toto eval-result example: qwen2.5-coder:3b-instruct-q2_K

Evidence for an example in-toto `eval-result` Statement (in-toto/attestation#565, #575) for the official Ollama tag `qwen2.5-coder:3b-instruct-q2_K` (model layer `sha256:14c4247b...`).

The run on 17 Nov 2026 used the released harness (`harness/audit.py`, unchanged since v3.4.1) on the 15-task screen (`smoke_suite_v1.json`). `run_record.json` was written before generation started. It records the manifest, model and chat-template digests, the runtime and the decode settings.

- `run_record.json`: digests, runtime (Ollama 0.32.6, Metal, Apple M2) and decode settings, written at run start
- `generations.jsonl`: the 15 model outputs
- `scored.json`: per-task EvalPlus 0.3.1 results (0 of 15 solved; the screen passes a tag at 9 or more)

The census run of 12 Aug 2026 (CUDA) gave the same result, 0 of 15.
