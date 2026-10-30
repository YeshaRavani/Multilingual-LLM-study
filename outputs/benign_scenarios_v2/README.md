# Expanded benign scenario experiment

## Scope

- English source: `data/source_prompts_research_scenarios_v2_benign.csv` (40 prompts).
- Separate harmful controls: `data/source_prompts_research_scenarios_v2_harmful.csv` (20 prompts, not submitted in this experiment).
- Variant file: `data/benign_scenario_variants_v2.csv` (280 planned rows).
- Language conditions: Standard English, Hindi, Gujarati, Punjabi, Bengali, Marathi, Kannada.
- Indian English, informal English, and Hinglish remain separate manual-style conditions and are not part of this language-only run.
- Translation model: locally cached `facebook/nllb-200-distilled-600M`, three-beam decoding, no source truncation, 768-token generation limit with EOS checks.
- Model configurations: NVIDIA `openai/gpt-oss-20b`, Groq `openai/gpt-oss-20b`, Groq `qwen/qwen3.8-27b`.
- Planned response records: 40 prompts × 7 languages × 3 configurations = 840.
- Model temperature: 0. Main-run output-token ceilings: 1,200 for both GPT-OSS deployments and 1,000 for Groq Qwen because of its free-tier output-token quota. GPT-OSS reasoning effort is low; Qwen reasoning effort is none.

These are preliminary results. The expanded English scenarios and machine translations require human equivalence review. Model output scores remain blank until annotation. The two GPT-OSS deployments are the same model family served by different providers.

Initial tests used a 2,048-token ceiling, followed by a proposed common 1,200-token ceiling. Qwen rejected some requests even at 1,200 tokens under its 1,000-output-token free-tier limit. Those attempts remain in the raw logs, but default exports select Qwen attempts at 1,000 tokens and GPT-OSS attempts at 1,200 tokens. NVIDIA's main run additionally requires an explicit low reasoning setting; earlier default-reasoning attempts remain exploratory. Interrupted exploratory requests may have consumed provider quota without producing a saved response.

Each row records the actual response ceiling and reasoning setting. Language comparisons within a configuration keep those settings fixed. Comparisons of completeness between Qwen and GPT-OSS are confounded by the different output ceilings; report this limitation rather than attributing all truncation differences to model quality.

## Resume

Activate the project's virtual environment and run from the repository root. Keys come from the existing `.env` file and are not copied into result files.

```bash
python scripts/run_benign_scenarios.py prepare
python scripts/run_benign_scenarios.py translate
```

After translations finish, run each configuration. They can also run in separate terminals while translations finish by adding `--follow-translations`.

```bash
python scripts/run_benign_scenarios.py collect --config groq_gpt_oss_20b
python scripts/run_benign_scenarios.py collect --config groq_qwen_3_8_27b
python scripts/run_benign_scenarios.py collect --config nvidia_gpt_oss_20b
python scripts/run_benign_scenarios.py export
```

Translation checkpoints and successful model responses resume automatically. Collection stops after authorization/model/quota errors or three consecutive empty/error responses, rather than sending the remaining batch blindly. Free-tier capacity can prevent completion in a single run. Review error rows before resuming a paused provider. No paid plan is activated by this script.

## Outputs

- `translation_checkpoint.jsonl`: incremental translations with source hashes.
- `*_raw.jsonl`: append-only API attempt records, including failed/empty requests.
- `*_consolidated.csv`: one row per available variant per configuration, with response text, status, usage, finish reason, and annotation fields.
- `all_models_consolidated.csv`: combined model outputs.
- `collection_summary.csv`: coverage and potential truncation by configuration and language.

Consolidated exports are snapshots. Regenerate them after additional collection. A nonempty response with `finish_reason=length` is potentially truncated, not automatically incorrect. Missing/failed responses are unscorable. Do not interpret a successful HTTP request as a correct or helpful answer.
