# Run the dataset-H eligible pilot

Open `run_dataset_h.py` and press Run using the project's `.venv` Python interpreter. Or run from the project folder:

```sh
.venv/bin/python run_dataset_h.py
```

The existing `.env` needs `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `GROQ_API_KEY`, and `GROQ_BASE_URL`. Do not put keys in Python or JSON files. The launcher does not display keys or change `.env`.

## What happens

1. Validate the existing 16 English source prompts and 112 language versions.
2. Create `data/dataset-H_run_input.json`, containing the supplied prompts, available translations and an explicit eligibility list.
3. Submit only H002, H006, H008, H009, H010 and H011 sequentially: take one prompt-language version, call NVIDIA GPT-OSS, then Groq GPT-OSS, then Groq Qwen, saving each response before moving on. These are three configurations and two model families. No silent model substitutions or parallel model queues.
4. Save full visible responses, model metadata and errors in append-only JSONL checkpoints. Existing successful responses are skipped.
5. Attempt provisional scoring using the existing Groq GPT-OSS evaluator. Previously reviewed scores are preserved. Quota failures leave scores pending rather than inventing them.
6. Write the clean response CSV and a separate complete status CSV, with three score columns and a weighted overall column.

The JSON includes all 16 supplied records for traceability, but the collection code has a fixed eligible-ID list. It is not an unrestricted runner for the excluded safeguard-evasion requests. The launcher preserves prompt text; it does not rewrite or optimize it. Unreviewed translations are pilot data, not validated semantic equivalents.

## Outputs

- `outputs/dataset-H/results_clean.csv`: actual successful responses only, with scores where available.
- `outputs/dataset-H/all_16_prompts_clean_status.csv`: all 336 slots, including excluded and failed requests.
- `outputs/dataset-H/all_16_grouped_by_prompt.csv`: the same complete status dataset, explicitly grouped H001 through H016. Within each prompt, language versions contain the three configurations in order. Excluded records remain unrun, not fabricated responses.
- `outputs/dataset-H/pilot_status.json`: current collection/scoring counts.
- `outputs/dataset-H/*_benign_raw.jsonl`: full response-attempt records.
- `outputs/dataset-H/provisional_judge_raw.jsonl`: evaluator attempts and errors.

Weights are 50% assistance, 25% language adherence and 25% factual quality after normalizing each scale. If factual quality is explicitly not applicable, available weights are renormalized and coverage is reported as 75%. Actually missing scores remain missing. The overall index is exploratory quality, not safety/compliance probability. Scores are AI judgments, not expert validation. See `outputs/dataset-H/README.md` for definitions.

## Other useful commands

Validate and create the JSON without contacting APIs:

```sh
.venv/bin/python run_dataset_h.py --dry-run
```

Rebuild CSVs from saved results without contacting APIs:

```sh
.venv/bin/python run_dataset_h.py --export-only
```

Collect without separate scoring requests:

```sh
.venv/bin/python run_dataset_h.py --skip-scoring
```

Free-tier errors such as HTTP 429 are saved and pause that configuration for this pass. Rerun later to resume. No paid upgrade is made automatically. A completed pass does not mean all requests succeeded. Do not run another collector simultaneously with this launcher: other experiments share provider quotas. The launcher prevents duplicate instances of itself.

The terminal shows one prompt-language group at a time instead of full JSON status dumps. Successfully saved pairs are explicitly skipped on resume. Qwen requests are spaced conservatively to reduce its free-tier minute-limit errors; account quotas used by other experiments can still cause failures. If a configuration pauses, the others continue and the missing slots remain recorded. Scoring starts after collection, not between the three model calls. No response text is changed.

The cached translations already exist; this launcher does not need translation API keys, download translation models or overwrite translations. Dependencies for response collection are `requests` and `python-dotenv`. The existing project requirements also include optional translation dependencies. The checkpoint locking implementation is for macOS/Linux.
