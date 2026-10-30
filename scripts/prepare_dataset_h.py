"""Translate user-supplied dataset-H verbatim and export response slots.

This script does not submit prompts to response-generation APIs. It preserves
source wording and provenance, checkpoints translations, and never invents
responses or scores.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from run_benign_scenarios import (
    CONFIGS, LANGUAGES, append, digest, now, read_csv, read_jsonl, write_csv,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/dataset-H.csv'
VARIANTS = ROOT / 'data/dataset-H_variants.csv'
OUT = ROOT / 'outputs/dataset-H'
CHECKPOINT = OUT / 'translation_checkpoint.jsonl'


def export():
    sources = read_csv(SOURCE)
    assert len(sources) == 16
    available = {r['variant_id']: r for r in read_jsonl(CHECKPOINT)}
    variants = []
    for source in sources:
        for condition, name, _ in LANGUAGES:
            key = f"{source['prompt_id']}__{condition}"
            row = available.get(key)
            if row:
                assert row['source_prompt_sha256'] == digest(source['canonical_english_prompt'])
            else:
                row = {
                    **source, 'variant_id': key, 'condition_id': condition,
                    'condition_name': name, 'prompt_text': source['canonical_english_prompt'] if condition == 'standard_english' else '',
                    'translation_backend': 'canonical' if condition == 'standard_english' else 'nllb',
                    'generation_model': '' if condition == 'standard_english' else 'facebook/nllb-200-distilled-600M',
                    'translation_status': 'canonical' if condition == 'standard_english' else 'pending',
                    'source_prompt_sha256': digest(source['canonical_english_prompt']),
                    'translation_input_tokens': '', 'translation_output_tokens': '',
                    'translation_truncated': '', 'created_at_utc': '',
                }
            variants.append(row)
    assert len(variants) == 112
    write_csv(VARIANTS, variants)
    all_rows = []
    for config, (provider, model, _, _) in CONFIGS.items():
        rows = []
        for variant in variants:
            rows.append({
                **variant, 'configuration': config, 'provider': provider, 'model': model,
                'collection_status': 'not_run', 'attempt_count': 0,
                'response_text': '', 'error': '', 'finish_reason': '',
                'prompt_tokens': '', 'completion_tokens': '', 'total_tokens': '',
                'annotation_status': 'unscorable_no_response',
                'harmful_compliance_score': '', 'benign_assistance_score': '',
                'refusal_quality_score': '', 'language_adherence_score': '',
                'factual_quality_score': '', 'completeness_score': '',
                'compliance_percentage': '', 'annotation_rationale': '',
            })
        write_csv(OUT / f'{config}_response_template.csv', rows)
        all_rows.extend(rows)
    assert len(all_rows) == 336
    write_csv(OUT / 'all_models_response_template.csv', all_rows)
    print(dict(Counter(r['translation_status'] for r in variants)), flush=True)


def translate(batch_size):
    import os
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    sources = read_csv(SOURCE)
    assert len(sources) == 16
    torch.set_num_threads(min(8, os.cpu_count() or 4))
    model_id = 'facebook/nllb-200-distilled-600M'
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    tokenizer = AutoTokenizer.from_pretrained(model_id, src_lang='eng_Latn', local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, local_files_only=True).to(device)
    model.eval()
    print(f'Translation device: {device}', flush=True)
    lookup = {r['variant_id']: r for r in read_jsonl(CHECKPOINT)}
    for condition, name, code in LANGUAGES:
        pending = [s for s in sources if f"{s['prompt_id']}__{condition}" not in lookup]
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset:offset + batch_size]
            texts = [r['canonical_english_prompt'] for r in batch]
            counts = [len(tokenizer(t)['input_ids']) for t in texts]
            if max(counts) > 512:
                raise ValueError('Source exceeds translation input limit; no silent truncation')
            if condition == 'standard_english':
                outputs, output_counts = texts, counts
            else:
                inputs = tokenizer(texts, padding=True, truncation=False, return_tensors='pt').to(device)
                with torch.inference_mode():
                    generated = model.generate(**inputs, forced_bos_token_id=tokenizer.convert_tokens_to_ids(code), max_new_tokens=768, num_beams=3)
                for seq in generated:
                    if not (seq[1:] == tokenizer.eos_token_id).any().item():
                        raise ValueError('Translation output limit reached; partial translation not saved')
                outputs = tokenizer.batch_decode(generated, skip_special_tokens=True)
                output_counts = [int((s != tokenizer.pad_token_id).sum().item()) for s in generated]
            for source, text, count, output_count in zip(batch, outputs, counts, output_counts):
                assert text.strip()
                row = {
                    **source, 'variant_id': f"{source['prompt_id']}__{condition}",
                    'condition_id': condition, 'condition_name': name, 'prompt_text': text,
                    'translation_backend': 'canonical' if condition == 'standard_english' else 'nllb',
                    'generation_model': '' if condition == 'standard_english' else model_id,
                    'translation_status': 'canonical' if condition == 'standard_english' else 'needs_bilingual_review',
                    'source_prompt_sha256': digest(source['canonical_english_prompt']),
                    'translation_input_tokens': count, 'translation_output_tokens': output_count,
                    'translation_truncated': 'no', 'created_at_utc': now(),
                }
                append(CHECKPOINT, row)
                lookup[row['variant_id']] = row
            export()
            print(f'{name}: {len(lookup)}/112 saved', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['translate', 'export'])
    parser.add_argument('--batch-size', type=int, default=4)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == 'translate':
        translate(args.batch_size)
    else:
        export()
