"""Run generation and scoring as separate processes for the fresh dataset."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_strategies import evaluate
from run_prompt_pipeline import load_prompts, load_results, merge_api_scores, save_csv


def save_status(args, state, summary=None, exit_code=None, phase=None):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    status = {"state": state, "phase": phase or args.stage, "pid": os.getpid(),
              "updated_at_utc": datetime.now(timezone.utc).isoformat(), "exit_code": exit_code}
    if summary:
        status.update(generated=summary["generated_responses"], scored=summary["scored_responses"],
                      expected=summary["expected_responses"],
                      generation_complete=summary["generation_complete"],
                      collection_complete=summary["collection_complete"],
                      observed_leaders=summary["observed_leaders"])
    temp = args.output_dir / "job_status.tmp"
    temp.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    temp.replace(args.output_dir / "job_status.json")


def refresh(args, *, merge_labels=True):
    labels = args.output_dir / 'api_scores.csv'
    final = args.output_dir / 'final_output.csv'
    if merge_labels and labels.exists() and final.exists():
        with final.with_suffix('.csv.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass  # The generator merges labels while it owns the final CSV.
            else:
                prompts = load_prompts(args.input)
                rows = load_results(final, prompts, True)
                merge_api_scores(rows, load_results(labels, prompts, True))
                save_csv(final, rows)
    return evaluate(args.input, args.output_dir / "final_output.csv", args.output_dir)


def stop_process(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)


def collect_parallel(commands, args, dry_run=False):
    if dry_run:
        return max(collect(command, args, phase, True) for phase, command in commands.items())
    with ExitStack() as stack:
        processes = {}
        try:
            for phase, command in commands.items():
                log = stack.enter_context((args.output_dir / 'scoring.log' if phase == 'score'
                                           else args.output_dir / 'generation.log').open('a'))
                processes[phase] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            last_refresh = 0
            while True:
                gen_code = processes['generate'].poll()
                score_code = processes['score'].poll()
                now = time.monotonic()
                if now - last_refresh >= 30:
                    # Never race the generator for its final-file lock at startup.
                    summary = refresh(args, merge_labels=gen_code is not None)
                    save_status(args, 'running', summary, phase='generate+score')
                    print(f"Progress: {summary['generated_responses']}/{summary['expected_responses']} generated; "
                          f"{summary['scored_responses']} scored; active stage=generate+score", flush=True)
                    last_refresh = now
                if gen_code not in (None, 0):
                    stop_process(processes['score'])
                    return gen_code
                # A failed scorer must not stop generation; surface it in its log.
                if gen_code is not None and score_code is not None:
                    refresh(args)
                    return max(gen_code, score_code)
                time.sleep(1)
        except KeyboardInterrupt:
            return 130
        finally:
            for process in processes.values():
                stop_process(process)


def collect(command, args, phase, dry_run=False):
    log_path = args.output_dir / ("generation.log" if phase == "generate" else "scoring.log")
    if not dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    with (log_path.open("a") if not dry_run else open(os.devnull, "w")) as log, \
         subprocess.Popen(command, stdout=None if dry_run else log, stderr=None if dry_run else subprocess.STDOUT) as process:
        while True:
            try:
                return process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                if not dry_run:
                    summary = refresh(args)
                    save_status(args, "running", summary, phase=phase)
                    print(f"Progress: {summary['generated_responses']}/{summary['expected_responses']} generated; "
                          f"{summary['scored_responses']} scored; active stage={phase}", flush=True)
            except KeyboardInterrupt:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait()
                return 130


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "data/translations/multilingual_prompts.csv")
    parser.add_argument("--output-dir", type=Path, default=HERE / "outputs/model_evaluation")
    parser.add_argument("--stage", choices=["generate", "score", "all", "parallel"], default="generate")
    parser.add_argument("--seed-from", type=Path, help="Existing combined CSV to import without regeneration")
    args, forwarded = parser.parse_known_args()
    if any(f in ("--output", "--responses") or f.startswith(("--output=", "--responses=")) for f in forwarded):
        parser.error("Use --output-dir; raw generation and scoring outputs are separate")
    if args.seed_from and args.stage == "score":
        parser.error("--seed-from belongs to generation")
    dry_run = "--dry-run" in forwarded
    base = [sys.executable, str(ROOT / "scripts/run_prompt_pipeline.py"), "--input", str(args.input)]
    if not dry_run:
        save_status(args, "running")
    if args.stage == 'parallel':
        labels = args.output_dir / 'api_scores.csv'
        final = args.output_dir / 'final_output.csv'
        if not dry_run:
            # The follower must be able to open its source on a brand-new run.
            for path in (args.output_dir / 'generated_responses.csv', final):
                if not path.exists():
                    save_csv(path, {})
        commands = {
            'generate': [*base, '--stage', 'generate', '--output', str(args.output_dir / 'generated_responses.csv'),
                         *forwarded, '--mirror-output', str(final), '--labels-input', str(labels)],
            'score': [*base, '--stage', 'score', '--output', str(labels), *forwarded,
                      '--responses', str(args.output_dir / 'generated_responses.csv'), '--seed-scores-from', str(final),
                      '--follow', '--poll-interval', '30', '--attempts', '1', '--timeout', '45'],
        }
        if args.seed_from:
            commands['generate'] += ['--seed-from', str(args.seed_from)]
        result = collect_parallel(commands, args, dry_run)
        if not dry_run:
            summary = refresh(args)
            save_status(args, 'complete' if summary['collection_complete'] else 'incomplete', summary, result)
        return result
    code = 0
    for phase in (["generate", "score"] if args.stage == "all" else [args.stage]):
        name = "generated_responses.csv" if phase == "generate" else "final_output.csv"
        command = [*base, "--stage", phase, "--output", str(args.output_dir / name), *forwarded]
        if phase == "generate":
            command += ["--mirror-output", str(args.output_dir / "final_output.csv")]
        if phase == "generate" and args.seed_from:
            command += ["--seed-from", str(args.seed_from)]
        if phase == "score":
            command += ["--responses", str(args.output_dir / "generated_responses.csv")]
        print(f"Starting independent {phase} process", flush=True)
        result = collect(command, args, phase, dry_run)
        code = max(code, result)
        if result not in (0, 1) or (phase == "generate" and result != 0):
            break
    if not dry_run:
        summary = refresh(args)
        done = summary["generation_complete"] if args.stage == "generate" else summary["collection_complete"]
        save_status(args, "complete" if done else "incomplete", summary, code)
        print(f"Saved {summary['generated_responses']} generated / {summary['scored_responses']} scored / "
              f"{summary['expected_responses']} expected", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
