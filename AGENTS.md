# Project instructions

## Model selection for future experiments

When the user asks to run prompts or experiments on the models, use exactly these
three configurations unless the user explicitly requests a different selection:

| Model | Provider | API model identifier |
| --- | --- | --- |
| Qwen (current project version) | Groq | `qwen/qwen3.8-27b` |
| GPT-OSS 20B | Groq | `openai/gpt-oss-20b` |
| Gemma 4 31B IT | NVIDIA | `google/gemma-4-31b-it` |

Gemma replaces the NVIDIA-hosted GPT-OSS configuration. Do not count the same
GPT-OSS model on two providers as two study models.

Existing scripts and documentation may still contain historical model defaults.
Before running them, explicitly configure and verify the three models above;
update runner support as necessary rather than relying on historical defaults.
If a selected endpoint fails, report the failure instead of silently substituting
another model. Preserve historical outputs and their original model labels, and
write new model responses with accurate provider/model metadata.

This instruction records the model selection; it does not itself request an API
run. Run experiments when the user asks for them.
