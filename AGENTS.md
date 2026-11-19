# Project instructions

## Model selection for future experiments

When the user asks to run prompts or experiments on the models, use exactly these
three configurations unless the user explicitly requests a different selection:

| Model | Provider | API model identifier |
| --- | --- | --- |
| Qwen (current project version) | Groq | `qwen/qwen3.8-27b` |
| GPT-OSS 20B | Groq (earlier NVIDIA responses retained) | `openai/gpt-oss-20b` |
| Nemotron 3.5 Bolt E4B | NVIDIA free prototype endpoint | `nvidia/nemotron-3.5-bolt-e4b` (thinking disabled) |

The user explicitly replaced Gemma with Bolt on 2026-11-05 after an eight-language
speed pilot. Remove Gemma from active response CSVs and comparisons, retaining
historical copies outside the repository. Never relabel Gemma responses as Bolt.
Do not count the same GPT-OSS model on two providers as two study models.

Existing scripts and documentation may still contain historical model defaults.
Before running them, explicitly configure and verify the three models above;
update runner support as necessary rather than relying on historical defaults.
If a selected endpoint fails, report the failure instead of silently substituting
another model. Preserve historical outputs and their original model labels, and
write new model responses with accurate provider/model metadata.

This instruction records the model selection; it does not itself request an API
run. Run experiments when the user asks for them.

Generation and scoring must run as independent stages. Generation saves raw
responses without judge calls; scoring reads those saved responses and writes
a separate final CSV. Preserve earlier responses and scores, record actual
providers in provenance sidecars, and do not enable paid fallback routes without
an agreed budget. Provider rate limits must not stall other ready generation
models. Do not reduce the input dataset or change prompts to improve throughput.

On 2026-11-11 the user selected `google/gemini-3.5-flash-lite` through the
existing Google API key as the independent API scorer and requested fresh
scoring for both studies. Use `--judge gemini-flash-lite` (the default), with
temperature 0, minimal thinking and JSON output. Archive the old GPT-OSS API
labels before clearing them; never seed this fresh run with the old judge's
labels. Preserve every generated response and direct semantic helpfulness review.
The judge choice is independent of generation route profiles. No paid fallback
or billing upgrade is authorized. Free-tier quotas can still limit throughput.
The user explicitly approved the prepared free provider changes on 2026-10-30
("go on, do whatever") after being asked to authorize Google for Gemma and
NVIDIA for GPT-OSS. On 2026-11-05 the user subsequently approved returning
GPT-OSS generation and API judging to Groq after repeated NVIDIA timeouts. Use
the `original` route profile for the current Qwen/GPT-OSS-on-Groq, Bolt-on-NVIDIA
run. The `distributed` profile retains the earlier NVIDIA GPT-OSS route. No paid
usage, tier upgrade, or different model is authorized by that provider approval.

The Bolt replacement and free NVIDIA testing/collection are additionally authorized
by the 2026-11-05 request. Keep the same input CSV, temperature and 1,000-token
generation budget. Publish new pending responses in the existing final_output.csv
as generation progresses, retaining earlier API labels and semantic judgments.
Generation makes no judge calls. In parallel mode, the API scorer follows raw
responses into api_scores.csv while the generator merges matching labels into
its locked final mirror. Preserve semantic judgments; concurrent API scoring only
produces refusal/completeness labels. Bolt's smaller model size and changed model lineup
must be documented in the research methodology.

On 2026-11-19 the user stopped further semantic helpfulness review for dataset-H.
Preserve its existing 51 judgments, but do not add more unless the user changes
that instruction. Future direct semantic review applies only to the benign
strategy dataset. Do not describe direct reviews as an unattended background job.
