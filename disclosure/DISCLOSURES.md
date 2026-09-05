# Upstream disclosure log

Every confirmed defect is reported to the registry that distributes the
artifact. This file tracks the reports.

| Defect | Registry | Report |
|---|---|---|
| `qwen2.5-coder:3b-instruct-q2_K` / `q3_K_S` / `q3_K_M` / `q3_K_L` (bad conversion batch) | Ollama official library | [ollama/ollama#18252](https://github.com/ollama/ollama/issues/18252), filed 2026-09-05 (UTC) as one report covering the batch |
| `phi3.5:3.8b-mini-instruct-q2_K` (isolated bad conversion) | Ollama official library | included in [ollama/ollama#18252](https://github.com/ollama/ollama/issues/18252) |

No defects were confirmed in community Hugging Face conversions, so no
reports are owed there. Two community files with backend-dependent behavior
were classified as backend-dependent failures, not defects; see the paper.
