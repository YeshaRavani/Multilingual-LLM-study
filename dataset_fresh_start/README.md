# Four-strategy multilingual benign dataset

40 original short benign prompts × 4 framing strategies × 8 languages = **1,280 input prompts**.

Strategies: persona builder, emotional stakes, task decomposition and audience framing.

Languages: English, Gujarati, Hindi, Punjabi (Gurmukhi), Kannada, Tamil, Malayalam and Marathi.

## Data files

- `data/original/base_prompts.csv`: 40 unchanged original short benign prompts, with ID and category.
- `data/original/english_strategy_prompts.csv`: 160 descriptive English versions.
- `data/translations/multilingual_prompts.csv`: complete 1,280-row dataset, exported only when every version exists and structural checks pass.
- `outputs/dataset_validation.json`: coverage and provenance checks.
- `docs/methodology.md`: framing definitions, translation method, adaptation boundaries and references.

The main dataset has seven columns: `variant_id`, `prompt_id`, `category`, `strategy`, `language`, `prompt_text`, `review_status`. It is ordered by original question, strategy, then language. Every original question is included verbatim in each of its four English expansions. IDs retain the original MSF numbering, so gaps in the numbering are expected; the 20 harmful controls are not included.

Translations are model-assisted with documented assistant-supplied corrections and fixed instruction units; they require bilingual review. English expansions are assistant-authored and require independent review. These are explicit review statuses, not missing data or model refusals. No LLM response collection or scoring is part of this build.

## Build or resume

From the existing CSS project folder:

```sh
.venv/bin/python dataset_fresh_start/build.py
```

This uses the existing cached NLLB translation model and existing `.env` location without copying API keys. Local translation does not spend response-generation API credits. It saves intermediate translations under `.build/` and resumes them on rerun. Translation is aligned by framing paragraph, original question and numbered part, so numbered subquestions cannot disappear and each base question has the same translation across strategies. Documented assistant terminology corrections are separate from raw translations. See the methodology for the exact procedure and limitations.

Recheck the finished CSV:

```sh
.venv/bin/python dataset_fresh_start/build.py --validate-only
```

Regenerate only the original and English-strategy CSVs:

```sh
.venv/bin/python dataset_fresh_start/build.py --english-only
```

The build uses the existing Python environment and the Codex-bundled Node/artifact runtime for CSV export. The previous datasets, outputs and scripts are untouched. Intermediate translation checkpoints and dependency symlinks are not version-controlled.

## Run response models and compare strategies

See [pipeline documentation](../PIPELINE.md) for setup, provider routes and recovery.
The active free routes are Qwen and GPT-OSS 20B on Groq and Nemotron 3.5 Bolt E4B
on NVIDIA. Inputs are read unchanged.

```sh
python dataset_fresh_start/run_models.py --stage parallel --route-profile original --accept-provider-change --resume
```

Results are written under `outputs/model_evaluation/`. Generation and API scoring
run simultaneously in independent processes. The API scorer uses a separate
checkpoint and its completed labels are merged into the final CSV. Generated responses are mirrored live into the existing
`final_output.csv`, retaining earlier scores. That file contains eight columns: prompt ID,
strategised prompt, model, response, status, binary refusal label, completeness
score and `semantic_helpfulness_score`. The semantic score is a direct holistic
assistant review on a 0–100 scale, not a weighted formula. New responses remain
blank until reviewed. Empty responses are unscored. Existing judgments are
preserved when the prompt and response are unchanged.

Strategy reports rank matched observations using semantic helpfulness; API
refusal/completeness coverage is reported separately. Reasons and content hashes
for direct reviews remain in `outputs/model_evaluation/semantic_review/decisions.jsonl`.
