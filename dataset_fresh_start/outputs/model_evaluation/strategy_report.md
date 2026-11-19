# Strategy evaluation

Generated **3,840 / 3,840** responses; scored **3,831 / 3,840**.
Saved responses: 3,840. Missing responses: 0.
Direct semantic reviews: **528 / 3,840**. Ranking metric: `semantic_helpfulness_score` (0–100).

**Provisional observed leader (incomplete semantic review): task_decomposition — 78.14/100.**

| Strategy | Matched semantic mean /100 | Reviewed / expected | Refusal % |
|---|---:|---:|---:|
| task_decomposition | 78.14 | 133/960 | 6.37 |
| persona_builder | 71.51 | 135/960 | 4.90 |
| audience_framing | 70.77 | 125/960 | 1.78 |
| emotional_stakes | 70.28 | 135/960 | 6.15 |

Ranking uses 124 matched question/language/model observations per strategy.
Component metrics in the CSV summaries use all available scored observations; coverage is shown separately.

Exploratory 95% cluster-bootstrap interval for the top-two score difference: [3.119, 9.664] points, resampling 40 base questions (2,000 draws).
The top two were selected from these data; this interval is descriptive, without multiple-comparison correction.

## Interpretation

Higher semantic helpfulness means better fulfillment of the actual benign prompt, considering relevance, correctness, coverage, clarity and language. Scores are holistic direct judgments, not calculated from API labels. Empty responses are excluded, not treated as refusals or zero scores. Truncated responses are reviewed on their visible content.
Only question/language/model cells directly reviewed for every strategy enter ranking. API scoring status does not determine eligibility for semantic ranking. Refusal and completeness summaries use the separate available API labels. Final CSV prompt_id corresponds to input variant_id; strategy and language are joined from the unchanged input.
When provenance is available, all strategies in a matched cell must also use the same target provider. Mixed-provider or missing-provenance cells do not enter the ranking, so a provider switch cannot be mistaken for a strategy effect.
Semantic scores are single-assistant annotations and require independent validation. Refusal/completeness are provisional automatic GPT-OSS labels, including self-evaluation. New responses remain without semantic scores until directly reviewed.
Generation and scoring are independent processes. Raw answers are in generated_responses.csv; scoring writes final_output.csv and never edits raw generations. Provider provenance is kept in CSV sidecars; existing Groq responses/labels are preserved alongside later provider routes.
Input review statuses: needs_bilingual_review=1120, needs_independent_review=160. Translation and wrapper differences can affect comparisons.
There is no unwrapped baseline in this run, so this comparison ranks the four strategies without estimating improvement over unwrapped prompts.
