# Upstream disclosure log

This file tracks what was reported to the registries that distribute the
audited artifacts, and every later correction.

## Status (2026-10): the v1 defect claims are withdrawn

Version 1 of the paper (arXiv:2609.05881v1) reported five Ollama library
artifacts as defective conversions, and they were reported upstream as such.
**These defect claims are withdrawn.** Rebuilt from the original checkpoints
with llama.cpp, each of the five files is an exact, uncalibrated
quantization of the released weights:

- the four `qwen2.5-coder:3b-instruct` tags (q2_K, q3_K_S, q3_K_M, q3_K_L)
  match our uncalibrated rebuild in all 434 tensors;
- `phi3.5:3.8b-mini-instruct-q2_K` matches our uncalibrated rebuild in all
  197 tensors when its 32 `attn_qkv` tensors are stored at `Q2_K`, an older
  llama.cpp type mix.

No file defect exists. The tags are still non-functional: each solves 0 of
164 HumanEval+ tasks. Calibrated builds of the same weights at the same
level work for four of the five. Qwen q2_K, q3_K_M and q3_K_L reach 76 to 113
of 164 with our own importance matrix; Qwen q3_K_S stays weak (13 to 30);
phi3.5 q2_K reaches 34 with a third-party importance matrix at the tag's own
tensor mix. Evidence: `rerun-2026-10/` in this repository, and the revised
paper (arXiv:2609.05881v2).

## Reports

| Artifact(s) | Registry | Report | Status |
|---|---|---|---|
| `qwen2.5-coder:3b-instruct-q2_K` / `q3_K_S` / `q3_K_M` / `q3_K_L` | Ollama official library | [ollama/ollama#18252](https://github.com/ollama/ollama/issues/18252), filed 2026-09-05 (UTC) as one report covering the four tags | **Defect claim withdrawn (2026-10).** Reported as a bad conversion batch, and reaffirmed on [2026-09-10](https://github.com/ollama/ollama/issues/18252#issuecomment-5612550620) against Qwen's own GGUF files, which are labeled `Instruct-AWQ` in their metadata (AWQ-scaled weights) and so are not uncalibrated referees either. The tags are uncalibrated quantizations, tensor-identical to our rebuild. They remain non-functional, and calibration rescues q2_K, q3_K_M and q3_K_L but not q3_K_S. Follow-up comment on the issue, withdrawing the defect claim and crediting the calibration hypothesis: [2026-10-27 (UTC)](https://github.com/ollama/ollama/issues/18252#issuecomment-6433255639) |
| `phi3.5:3.8b-mini-instruct-q2_K` | Ollama official library | Included in [ollama/ollama#18252](https://github.com/ollama/ollama/issues/18252) | **Withdrawn on [2026-09-10](https://github.com/ollama/ollama/issues/18252#issuecomment-5612550620) (UTC).** The reason given then was wrong: the no-imatrix lm-kit upload cited as an independent referee carries the library file's tensors. The tag is an uncalibrated quantization with an older tensor mix (tensor-identical to our rebuild with that mix), non-functional, and rescued in part by calibration. |

The two `llama3.2:1b-instruct` tags (q2_K, q3_K_S) are also non-functional
(0 and 6 of 164). Their checkpoint is licence-gated and was not rebuilt, so
their cause is not attributed, and no report was filed.

No defects were confirmed in community Hugging Face conversions, so no
reports are owed there. Two community files fail without an instruction
template and work with one; they are classified as template-dependent failures,
not file defects (v3.4; the v2 preprint called them backend-dependent).

## Referee independence

A different repository name or whole-file hash does not show an independent
conversion. The library's phi3.5 q2_K file (`sha256 54d47caa…`) is
byte-identical to uploads under `QuantFactory/Phi-3.5-mini-instruct-GGUF` and
`neopolita/phi-3.5-mini-instruct-gguf`, as checked from registry and
Hugging Face headers on the issue on
[2026-09-11](https://github.com/ollama/ollama/issues/18252#issuecomment-5629686876).
It is also tensor-identical, with one added metadata key, to the upload under
`lm-kit/phi-3.5-mini-3.8b-instruct-gguf`. The QuantFactory and lm-kit file
and tensor hashes are in `rerun-2026-10/local_referee_hashes.jsonl`. Referees
are now compared with the suspect tensor by tensor
(`rerun-2026-10/scripts/compare_tensors.py`).
