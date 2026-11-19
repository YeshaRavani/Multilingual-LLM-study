# Multilingual LLM study

Compare four prompt strategies across 40 benign questions and eight languages
using Qwen, GPT-OSS 20B and Nemotron 3.5 Bolt E4B. The team's 1,280 input prompts are in
`dataset_fresh_start/data/translations/multilingual_prompts.csv`.

## Setup and run

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Add free-provider credentials to .env using .env.example.
python dataset_fresh_start/run_models.py --stage parallel --route-profile original --accept-provider-change --resume
```

Generation and API scoring run simultaneously as separate processes. Resume reuses saved
responses and scores. Current routes are Qwen and GPT-OSS through Groq, and Bolt through NVIDIA. No paid fallback is configured.
Gemini 3.5 Flash-Lite on Google independently supplies refusal/completeness
labels (`--judge gemini-flash-lite`, the default), using `GEMINI_API_KEY`.

Results are in `dataset_fresh_start/outputs/model_evaluation/`:

- `generated_responses.csv`: saved model responses and collection checkpoints.
- `final_output.csv`: live responses, refusal/completeness labels and independent semantic reviews.
- `strategy_report.md`: matched strategy comparison using semantic helpfulness.

The final CSV contains `prompt_id`, `strategised_prompt`, `model`, `response`,
`status`, `binary_refusal_label`, `completeness_score` and
`semantic_helpfulness_score`. Semantic scores are direct assistant judgments
(0–100), not a formula or API-generated composite. New responses remain blank
in that column until directly reviewed.

See [PIPELINE.md](PIPELINE.md) for commands, recovery and evaluation details,
and [dataset documentation](dataset_fresh_start/README.md) for the input design.
New generated responses are published into the same final CSV immediately;
existing labels and semantic scores are retained. Bolt uses thinking disabled.
The dataset builder and its source CSV are retained; this pipeline does not
create or modify prompts.

## Dataset-H and scoring coverage

Dataset-H has a separate result file at
`dataset_fresh_start/outputs/dataset_H_multilingual/final_output.csv`.
It contains 16 base questions in eight languages across three models (384
responses), with no separate four-strategy conditions. All 384 responses have
Gemini refusal/completeness labels. Its completeness rubric measures safe
response quality, including appropriate refusal, rather than obedience to
harmful requests. The benign dataset instead rewards useful fulfillment of
safe requests.

As of the 2026-11-19 snapshot, the benign dataset has 3,831/3,840 API-scored
responses and 528 direct semantic reviews. Dataset-H has 51 direct semantic
reviews. On the user's instruction, further semantic review applies only to
the benign dataset; dataset-H's remaining semantic cells stay blank. Missing
semantic reviews are not zeros. Semantic strategy rankings remain preliminary
until adequate matched review coverage is available for every model and language.

The latest slide deck is in `output/`; it appends dataset-H examples and
observations to the historical proposal. Earlier slides retain the original
proposal's model, budget and scoring plans.

## Offline checks

```sh
python -m unittest discover -s scripts -p 'test_*.py'
python -m unittest discover -s dataset_fresh_start/scripts -p 'test_*.py'
```

Historical experiments and redundant artifacts were moved out of the codebase
to the sibling `Multilingual-LLM-study-archive-2026-11-01/` directory. Its
`cleanup_manifest.json` lists the archived paths. Credentials, current input
datasets, live checkpoints and semantic review decisions remain in this project.
