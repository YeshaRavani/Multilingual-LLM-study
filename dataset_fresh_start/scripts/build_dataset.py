"""Prepare and translate the four-strategy benign dataset. No response collection.

Uses the existing project's cached NLLB model. API keys are not printed or
required for local translation. Final CSV authoring is handled by export_dataset.mjs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time

from strategy_content import CONTENT, LANGUAGES, STRATEGIES, expand

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
BUILD = ROOT / '.build'
ENGLISH = BUILD / 'english.json'
CHECKPOINT = BUILD / 'translations_aligned.jsonl'
CHUNKS = BUILD / 'chunk_translations.jsonl'
MODEL = 'facebook/nllb-200-distilled-600M'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def prepare():
    with (PROJECT / 'data/source_prompts_research_v1.csv').open(encoding='utf-8', newline='') as f:
        sources = [r for r in csv.DictReader(f) if r['expected_outcome'] == 'answer']
    assert len(sources) == 40 and {r['prompt_id'] for r in sources} == set(CONTENT)
    originals = [{'prompt_id': r['prompt_id'], 'category': r['category'], 'original_prompt': r['canonical_english_prompt']} for r in sources]
    english = []
    for source in sources:
        for strategy in STRATEGIES:
            text = expand(source, strategy)
            assert source['canonical_english_prompt'] in text
            english.append({
                'variant_id': f"{source['prompt_id']}__{strategy}__en",
                'prompt_id': source['prompt_id'], 'category': source['category'],
                'strategy': strategy, 'language': 'English', 'language_code': 'en',
                'prompt_text': text, 'review_status': 'needs_independent_review',
                'source_sha256': sha(source['canonical_english_prompt']),
                'english_sha256': sha(text),
            })
    assert len(english) == 160 and len({r['prompt_text'] for r in english}) == 160
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'originals.json').write_text(json.dumps(originals, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ENGLISH.write_text(json.dumps(english, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Prepared 40 unchanged short benign prompts and 160 English strategy versions.', flush=True)
    return english


def checkpoint():
    records = []
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text(encoding='utf-8').splitlines():
            if line.strip():
                records.append(json.loads(line))
    return {r['variant_id']: r for r in records}


def parts(english):
    paragraphs = english['prompt_text'].split('\n\n')
    if english['strategy'] == 'task_decomposition':
        steps = [line.split('. ', 1)[1] for line in paragraphs[2].splitlines()]
        return [paragraphs[0], paragraphs[1], *steps]
    return paragraphs


def read_chunks():
    if not CHUNKS.exists():
        return {}
    rows = [json.loads(line) for line in CHUNKS.read_text(encoding='utf-8').splitlines() if line.strip()]
    return {(r['language_code'], r['chunk_sha256']): r for r in rows}


def assemble(english):
    lookup = read_chunks()
    overrides = json.loads((ROOT / 'scripts/chunk_overrides.json').read_text(encoding='utf-8'))['units']
    for unit in overrides:
        for code, text in unit['translations'].items():
            lookup[(code, sha(unit['english_text']))] = {'translation': text, 'source': 'documented_assistant_translation'}
    rows = []
    for code, language, _ in LANGUAGES:
        if code == 'en':
            continue
        for e in english:
            keys = [(code, sha(text)) for text in parts(e)]
            if not all(key in lookup for key in keys):
                continue
            translated = [lookup[key]['translation'] for key in keys]
            text = '\n\n'.join(translated[:2])
            if len(translated) > 2:
                text += '\n\n' + '\n'.join(f'{i}. {t}' for i, t in enumerate(translated[2:], 1))
            rows.append({**e, 'variant_id': f"{e['prompt_id']}__{e['strategy']}__{code}",
                         'language': language, 'language_code': code, 'prompt_text': text,
                         'review_status': 'needs_bilingual_review', 'translation_model': MODEL,
                         'translation_truncated': False, 'translation_method': 'aligned_paragraphs_and_numbered_parts',
                         'assistant_supplied_chunk_sha256s': [key[1] for key in keys if lookup[key].get('source') == 'documented_assistant_translation'],
                         'chunk_sha256s': [key[1] for key in keys]})
    temporary = CHECKPOINT.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    temporary.replace(CHECKPOINT)
    return len(rows)


def status():
    english = json.loads(ENGLISH.read_text(encoding='utf-8'))
    lookup = checkpoint()
    counts = {name: sum(f"{e['prompt_id']}__{e['strategy']}__{code}" in lookup for e in english) for code, name, _ in LANGUAGES if code != 'en'}
    result = {'expected_rows': 1280, 'english_rows': len(english), 'translated_rows': len(lookup), 'by_language': counts,
              'remaining_translations': 1120 - len(lookup), 'all_translations_require_bilingual_review': True}
    (BUILD / 'progress.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def translate(batch_size=8, limit_batches=None):
    os.environ.setdefault('USE_TF', '0')
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    import torch
    from dotenv import load_dotenv
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    load_dotenv(PROJECT / '.env', override=False)
    english = prepare()
    lookup = read_chunks()
    overrides = json.loads((ROOT / 'scripts/chunk_overrides.json').read_text(encoding='utf-8'))['units']
    for unit in overrides:
        for code, text in unit['translations'].items():
            lookup[(code, sha(unit['english_text']))] = {'translation': text, 'source': 'documented_assistant_translation'}
    torch.set_num_threads(4)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    dtype = torch.float16 if device == 'mps' else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(MODEL, src_lang='eng_Latn', local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, local_files_only=True, torch_dtype=dtype).to(device)
    model.eval()
    print(f'Local translation: {MODEL}, device={device}, dtype={dtype}, batch={batch_size}', flush=True)
    batches = 0
    unique = {}
    for e in english:
        for text in parts(e):
            unique.setdefault(sha(text), text)
    print(f'Aligned translation: {len(unique)} unique text units per language; shared questions translated once.', flush=True)
    for code, language, model_code in LANGUAGES:
        if code == 'en':
            continue
        pending = []
        for key, text in unique.items():
            if (code, key) not in lookup:
                pending.append((key, text))
        for offset in range(0, len(pending), batch_size):
            if limit_batches is not None and batches >= limit_batches:
                print(json.dumps(status()), flush=True)
                return
            batch = pending[offset:offset + batch_size]
            started = time.monotonic()
            texts = [text for _, text in batch]
            counts = [len(tokenizer(t)['input_ids']) for t in texts]
            if max(counts) > 512:
                raise ValueError('Input exceeds 512 tokens; no truncation permitted')
            inputs = tokenizer(texts, padding=True, truncation=False, return_tensors='pt').to(device)
            with torch.inference_mode():
                generated = model.generate(**inputs, forced_bos_token_id=tokenizer.convert_tokens_to_ids(model_code),
                                           max_new_tokens=256, num_beams=1, do_sample=False, no_repeat_ngram_size=3)
            sequences = [sequence.cpu() for sequence in generated]
            del inputs, generated
            if device == 'mps':
                torch.mps.synchronize()
                torch.mps.empty_cache()
            beams = [1] * len(sequences)
            for i, sequence in enumerate(sequences):
                if not (sequence[1:] == tokenizer.eos_token_id).any().item():
                    print(f'Retrying one {language} unit with beam search after a repetition/length limit.', flush=True)
                    single = tokenizer(texts[i], return_tensors='pt', truncation=False).to(device)
                    with torch.inference_mode():
                        recovered = model.generate(**single, forced_bos_token_id=tokenizer.convert_tokens_to_ids(model_code),
                                                   max_new_tokens=384, num_beams=3, do_sample=False, no_repeat_ngram_size=3)[0].cpu()
                    if not (recovered[1:] == tokenizer.eos_token_id).any().item():
                        raise ValueError(f'{language}: one unit still incomplete after retry; checkpoint preserved')
                    sequences[i] = recovered
                    beams[i] = 3
                    del single
            outputs = [tokenizer.decode(sequence, skip_special_tokens=True) for sequence in sequences]
            with CHUNKS.open('a', encoding='utf-8') as f:
                for (key, original_text), text, input_count, seq, beam in zip(batch, outputs, counts, sequences, beams):
                    if not text.strip() or text.strip() == original_text.strip():
                        raise ValueError('Empty or untranslated output; batch needs review')
                    row = {'chunk_sha256': key, 'english_text': original_text, 'translation': text.strip(),
                           'language': language, 'language_code': code, 'translation_model': MODEL,
                           'translation_input_tokens': input_count,
                           'translation_output_tokens': int((seq != tokenizer.pad_token_id).sum().item()),
                           'translation_truncated': False, 'translation_device': device, 'translation_precision': str(dtype),
                           'translation_batch_size': batch_size, 'translation_num_beams': beam,
                           'no_repeat_ngram_size': 3, 'generation_max_new_tokens': 384 if beam == 3 else 256}
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                    lookup[(code, key)] = row
            del sequences
            if device == 'mps':
                torch.mps.synchronize()
                torch.mps.empty_cache()
            batches += 1
            assemble(english)
            counts_now = status()
            print(f"{language}: {counts_now['by_language'][language]}/160 assembled; {len(lookup)} units translated; batch {time.monotonic()-started:.1f}s", flush=True)
    assert assemble(english) == 1120
    print('All 1120 translations generated. Bilingual review still required.', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['prepare', 'translate', 'status'])
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--limit-batches', type=int)
    args = p.parse_args()
    if args.stage == 'prepare':
        prepare()
    elif args.stage == 'translate':
        translate(args.batch_size, args.limit_batches)
    else:
        print(json.dumps(status(), indent=2))
