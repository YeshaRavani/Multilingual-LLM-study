# Multilingual LLM safety-fairness pilot

This project creates a paired prompt dataset and records model responses for a small multilingual safety-fairness study.

## What is generated

- `data/source_prompts.csv` contains only the six canonical English prompts.
- `scripts/build_variants.py` writes `data/variants.csv`, with ten conditions per source prompt.
- `scripts/collect_responses.py` writes raw API outputs to `outputs/responses.jsonl`.

The code automatically creates the six native-language translations using a free local model: Hindi, Gujarati, Punjabi, Bengali, Marathi, and Kannada. Set `TRANSLATION_BACKEND=indictrans2` for AI4Bharat IndicTrans2 after Hugging Face approves gated-model access, or use the ungated `TRANSLATION_BACKEND=nllb` fallback. It copies Standard English directly from the source prompt. Google Cloud Translation remains available as an optional backend by setting `TRANSLATION_BACKEND=google` and adding `GOOGLE_TRANSLATE_API_KEY`.

Indian English, Informal English, and Hinglish require a human-written or human-reviewed version. The script creates `data/manual_style_variants_template.csv`; copy it to `data/manual_style_variants.csv`, fill `prompt_text`, and rebuild the variant file. This protects the study from treating machine-generated style rewrites as ground truth.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your keys and selected, version-pinned model identifiers to `.env`. For Llama, use an OpenAI-compatible inference provider and set its endpoint in `LLAMA_BASE_URL` without the `/chat/completions` suffix.

For IndicTrans2, accept the model access terms on Hugging Face and add a read-only token as `HUGGINGFACE_TOKEN`. The first translation run downloads the model; later runs reuse the local cache.

## Run

```bash
python scripts/build_variants.py
# Complete data/manual_style_variants.csv, then rerun the previous command.
python scripts/prepare_pilot.py
python scripts/apply_reviews.py
python scripts/collect_responses.py --dry-run
python scripts/collect_responses.py
```

For the temporary no-cost professor pilot, use Gemini's free tier, GPT-OSS 20B
through Groq, and Llama 3.3 70B through OpenRouter:

```bash
python scripts/collect_responses.py \
  --providers gemini groq openrouter \
  --variants data/pilot_variants_reviewed.csv \
  --output outputs/pilot_free_models.jsonl
```

The OpenRouter free plan permits 50 requests per day. Keep the first pilot at
four source prompts across ten conditions, or split a larger collection across
multiple days.

To use the 60-prompt research dataset instead of the six-prompt pilot:

```bash
python scripts/build_variants.py \
  --source data/source_prompts_research_v1.csv \
  --output data/research_variants_v1.csv \
  --manual-file data/research_manual_styles_v1.csv \
  --manual-template data/research_manual_styles_template_v1.csv
```

This produces 600 prompt variants before model collection. With three model families, one run produces 1,800 responses.

After completing and validating the manual style file, collect the research responses with:

```bash
python scripts/collect_responses.py \
  --variants data/research_variants_v1.csv \
  --output outputs/research_responses_v1.jsonl
```

The final command produces 180 records for the initial pilot: 6 source prompts × 10 conditions × 3 model families. It stores every raw response, provider/model metadata, prompt metadata, and request status. Add annotation columns or a separate annotation file after collection; do not overwrite raw responses.

For a preliminary NVIDIA language-only run that excludes Indian English,
Informal English, and Hinglish:

```bash
python scripts/collect_responses.py \
  --providers nvidia \
  --variants data/variants.csv \
  --conditions standard_english hindi gujarati punjabi bengali marathi kannada \
  --allow-unreviewed-translations \
  --resume \
  --output outputs/preliminary_nvidia_gpt_oss_20b_languages.jsonl
```

These records are labelled preliminary because the machine translations have
not yet passed bilingual human review.
