"""Independent read-only checks for the final clean CSV."""
import csv
import json
from collections import Counter
from pathlib import Path

from strategy_content import LANGUAGES, STRATEGIES

ROOT = Path(__file__).resolve().parents[1]
HEADER = ['variant_id', 'prompt_id', 'category', 'strategy', 'language', 'prompt_text', 'review_status']
SCRIPT_RANGES = {'Gujarati': (0x0A80, 0x0AFF), 'Hindi': (0x0900, 0x097F),
                 'Punjabi': (0x0A00, 0x0A7F), 'Kannada': (0x0C80, 0x0CFF),
                 'Tamil': (0x0B80, 0x0BFF), 'Malayalam': (0x0D00, 0x0D7F),
                 'Marathi': (0x0900, 0x097F)}


def validate():
    with (ROOT / 'data/translations/multilingual_prompts.csv').open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == HEADER
        rows = list(reader)
    originals = {r['prompt_id']: r['original_prompt'] for r in csv.DictReader((ROOT / 'data/original/base_prompts.csv').open(encoding='utf-8'))}
    assert len(originals) == 40 and len(rows) == 1280
    assert len({r['variant_id'] for r in rows}) == 1280
    assert len({r['prompt_text'] for r in rows}) == 1280
    assert set(r['prompt_id'] for r in rows) == set(originals)
    assert set(r['strategy'] for r in rows) == set(STRATEGIES)
    languages = {name for _, name, _ in LANGUAGES}
    assert set(r['language'] for r in rows) == languages
    expected = {(p, s, l) for p in originals for s in STRATEGIES for l in languages}
    assert {(r['prompt_id'], r['strategy'], r['language']) for r in rows} == expected
    suspicious = []
    questions = {}
    for r in rows:
        assert r['prompt_text'].strip() and '\ufffd' not in r['prompt_text']
        paragraphs = r['prompt_text'].split('\n\n')
        assert len(paragraphs) == (3 if r['strategy'] == 'task_decomposition' else 2)
        questions.setdefault((r['prompt_id'], r['language']), set()).add(paragraphs[1])
        if r['strategy'] == 'task_decomposition':
            assert paragraphs[2].startswith('1. ') and '\n2. ' in paragraphs[2]
        if r['prompt_id'] == 'MSF-010':
            assert 'The manager killed the lights before the presentation,' in r['prompt_text']
            assert "'killed'" in r['prompt_text']
        if r['language'] == 'English':
            assert originals[r['prompt_id']] in r['prompt_text']
            assert r['review_status'] == 'needs_independent_review'
        else:
            assert r['review_status'] == 'needs_bilingual_review'
            low, high = SCRIPT_RANGES[r['language']]
            letters = [c for c in r['prompt_text'] if c.isalpha()]
            share = sum(low <= ord(c) <= high for c in letters) / max(1, len(letters))
            if share < 0.50:
                suspicious.append({'variant_id': r['variant_id'], 'target_script_share': round(share, 3)})
    assert not suspicious, f'Unexpected writing system: {suspicious}'
    assert all(len(q) == 1 for q in questions.values()), 'Base question differs across strategies'
    print(json.dumps({'status': 'PASS', 'rows': len(rows), 'columns': len(HEADER),
                      'language_counts': dict(Counter(r['language'] for r in rows)),
                      'strategy_counts': dict(Counter(r['strategy'] for r in rows)),
                      'missing_or_duplicate_combinations': 0,
                      'unexpected_script_flags': suspicious, 'bilingual_validation': 'still_required'}, indent=2))


if __name__ == '__main__':
    validate()
