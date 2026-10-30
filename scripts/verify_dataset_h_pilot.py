"""Read-only integrity checks for the dataset-H benign pilot CSVs."""
from collections import Counter

from run_dataset_h_benign import CONFIGS, ELIGIBLE, OUT, RUBRIC_VERSION, digest, read_csv, read_jsonl

rows = read_csv(OUT / 'all_models_consolidated.csv')
assert len(rows) == 336
assert len({(r['configuration'], r['variant_id']) for r in rows}) == 336
annotations = {r['evaluation_id']: r for r in read_jsonl(OUT / 'assistant_review_annotations.jsonl')}
annotations.update({r['evaluation_id']: r for r in read_jsonl(OUT / 'provisional_judge_raw.jsonl') if r.get('judge_status') == 'success'})
for r in rows:
    assert r['configuration'] in CONFIGS
    assert r['source_prompt_sha256'] == digest(r['canonical_english_prompt'])
    if r['condition_id'] == 'standard_english':
        assert r['prompt_text'] == r['canonical_english_prompt']
    if r['prompt_id'] not in ELIGIBLE:
        assert r['collection_status'] == 'excluded_not_eligible'
        assert not r['response_text']
    if r['collection_status'] != 'success':
        assert not r['benign_assistance_score']
        assert not r['benign_assistance_percentage']
    if r['benign_assistance_score']:
        assert r['response_text'] and r['collection_status'] == 'success'
        eid = digest(r['configuration'] + r['variant_id'] + r['response_text'] + RUBRIC_VERSION)
        assert eid in annotations
        assert float(r['benign_assistance_percentage']) == 25 * int(r['benign_assistance_score'])
        for field, maximum in [('benign_assistance_score', 4), ('language_adherence_score', 2), ('factual_quality_score', 2)]:
            if r[field] != '':
                assert 0 <= int(r[field]) <= maximum
    assert not r['compliance_percentage']
    assert not r['harmful_compliance_score']
    assert r['human_review_status'] == 'not_reviewed'
for config in CONFIGS:
    for attempt in read_jsonl(OUT / f'{config}_benign_raw.jsonl'):
        assert attempt['prompt_id'] in ELIGIBLE
        assert attempt['expected_outcome'] == 'answer'
        assert attempt['model'] == CONFIGS[config][1]
print('PASS: 336 unique rows, exact English/source hashes, only six eligible IDs submitted, hash-linked score provenance, valid ranges, no fabricated output or failure scores.')
print(dict(Counter(r['collection_status'] for r in rows)))
