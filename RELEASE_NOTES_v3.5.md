# quantcheck v3.5

Adds an in-toto record for a screen. No data, census script or analysis value changes from v3.4.1.

- `harness/screen_intoto.py` screens one Ollama tag and writes an in-toto Statement with the eval-result predicate proposed in in-toto/attestation pull request 575 (v0.1). Before generation it writes a run record with the manifest, model and chat-template digests, each checked against its blob and against the manifest the running server lists, plus the runtime, the decode settings and the HumanEval+ data version. It scores the 15 reference solutions first and stops unless all pass, generates with the unchanged `harness/audit.py`, checks that the tag and the served template did not change during the run, and scores with the corrected scorer used for the paper (`rerun-2026-10/scripts/score_runs.py`).
- `harness/intoto.py` builds a Statement from a finished screen and checks Statements against the predicate. `check --fetch` also downloads the linked evidence and compares digests. Standard library only.
- On macOS, EvalPlus 0.3.1 cannot set its memory limit, and every test then fails without an error. `screen_intoto.py` sets `EVALPLUS_MAX_MEMORY_BYTES=-1` there unless it is already set, and the reference-solution check stops any run whose scoring is broken. The released Metal results in `results-mac/` and `results-metalrep/` are not affected: their scores include 13 and 15 of 15, and their five zero scores are unchanged, task by task, when rescored with the setting.
- `tests/test_intoto.py`: 62 tests, standard library only (`python3 -m unittest discover -s tests`). One rebuilds, byte for byte, the Statement posted on in-toto/attestation issue 565 on 17 Nov 2026, now in `examples/intoto/qwen2.5-coder-3b-instruct-q2_K/statement.json`.
- README: a section "Write an in-toto record for a screen". CITATION.cff: version 3.5, and the note records the paper's acceptance at the IEEE BigData 2026 workshop TrustAI-BD.

The idea of a per-tag screen receipt came from Sattyam Jain (quantcheck issue 2).

The paper it supports is arXiv:2609.05881. Code: MIT. Data: CC BY 4.0.
