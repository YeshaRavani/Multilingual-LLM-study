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
