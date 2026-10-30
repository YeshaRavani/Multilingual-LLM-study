"""Build the 40 × 4 × 8 benign prompt dataset, resuming cached translations."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--english-only', action='store_true')
    args = parser.parse_args()
    if not importlib.util.find_spec('transformers'):
        executable = PROJECT / '.venv/bin/python'
        if executable.exists() and str(executable) != sys.executable:
            os.execv(str(executable), [str(executable), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit('Use the existing project .venv with transformers and torch installed.')
    sys.path.insert(0, str(ROOT / 'scripts'))
    from build_dataset import prepare, translate
    from validate_dataset import validate
    if args.validate_only:
        validate()
        return
    if args.english_only:
        prepare()
    else:
        translate(args.batch_size)
    dependency_root = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
    node = os.getenv('DATASET_NODE') or str(dependency_root / 'bin/node')
    if not Path(node).exists():
        node = shutil.which('node')
    if not node:
        raise SystemExit('Translations saved. Node runtime is needed for the checked CSV export.')
    modules = ROOT / 'scripts/node_modules'
    if not modules.exists() and (dependency_root / 'node_modules').exists():
        modules.symlink_to(dependency_root / 'node_modules', target_is_directory=True)
    command = [node, str(ROOT / 'scripts/export_dataset.mjs')]
    if args.english_only:
        command.append('--english-only')
    subprocess.run(command, check=True, cwd=ROOT)
    if not args.english_only:
        validate()


if __name__ == '__main__':
    main()
