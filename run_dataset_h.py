"""Press Run in your editor, or execute: .venv/bin/python run_dataset_h.py

Ready-to-run, resumable collection for the fixed eligible dataset-H subset.
Other prompts are retained in the JSON/status table but are not submitted.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def dependencies():
    if all(importlib.util.find_spec(name) for name in ('requests', 'dotenv')):
        return
    executable = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if executable.exists() and Path(sys.executable) != executable:
        os.execv(str(executable), [str(executable), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit('Install dependencies first: python -m pip install requests python-dotenv')


def prepare_json(core):
    sources = core.read_csv(ROOT / 'data/dataset-H.csv')
    variants = core.read_csv(core.VARIANTS)
    if len(sources) != 16 or len(variants) != 112:
        raise ValueError('Expected exactly 16 prompts and 112 language versions')
    source_by_id = {r['prompt_id']: r for r in sources}
    if len(source_by_id) != 16:
        raise ValueError('Duplicate source IDs')
    for v in variants:
        source = source_by_id[v['prompt_id']]
        if v['canonical_english_prompt'] != source['canonical_english_prompt']:
            raise ValueError('Variant does not match current source text')
        if v['source_prompt_sha256'] != core.digest(source['canonical_english_prompt']):
            raise ValueError('Stale translation source hash')
    document = {
        'schema_version': 'dataset-H-run-input-v1',
        'created_at_utc': core.now(),
        'eligible_prompt_ids': sorted(core.ELIGIBLE),
        'scope': 'Fixed eligible subset only. Other supplied prompts are archival, not submitted.',
        'prompts': [{**r, 'run_eligible': r['prompt_id'] in core.ELIGIBLE} for r in sources],
        'variants': variants,
    }
    core.INPUT_JSON.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return core.load_variants()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Validate/prepare JSON; no API calls')
    parser.add_argument('--export-only', action='store_true', help='Rebuild clean CSVs from saved results without API calls')
    parser.add_argument('--skip-scoring', action='store_true', help='Collect responses without additional judge calls')
    args = parser.parse_args()
    dependencies()
    sys.path.insert(0, str(ROOT / 'scripts'))
    import run_dataset_h_benign as core
    from dotenv import load_dotenv
    import fcntl

    core.OUT.mkdir(parents=True, exist_ok=True)
    with (core.OUT / '.launcher.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('This launcher is already running. Wait for it to finish.')
        variants = prepare_json(core)
        eligible = [v for v in variants if v['prompt_id'] in core.ELIGIBLE and v['prompt_text'].strip()]
        print(f'JSON prepared: 16 source prompts, {len(variants)} language slots.')
        print(f'Eligible IDs: {", ".join(sorted(core.ELIGIBLE))}')
        print(f'Available eligible variants: {len(eligible)}/42; configurations: 3.')
        print('All generated translations remain preliminary until bilingual review.')
        print('Order: one prompt-language version -> NVIDIA GPT-OSS -> Groq GPT-OSS -> Groq Qwen.')
        if args.dry_run:
            print('Validation passed. No API calls made.')
            return
        if args.export_only:
            core.export()
            return
        load_dotenv(ROOT / '.env', override=False)
        needed = {name for _, _, api_key, base in core.CONFIGS.values() for name in (api_key, base)}
        missing = sorted(key for key in needed if not os.getenv(key))
        if missing:
            raise SystemExit('Missing .env settings: ' + ', '.join(missing))
        try:
            core.collect_sequential()
            if not args.skip_scoring:
                print('\nStarting provisional scoring of saved responses...', flush=True)
                core.score()
        except KeyboardInterrupt:
            print('Interrupted. Saved checkpoints will be used on the next run.')
        finally:
            core.export()
        print('Saved: outputs/dataset-H/results_clean.csv')
        print('Check pilot_status.json: a finished pass can still have quota errors or pending scores.')


if __name__ == '__main__':
    main()
