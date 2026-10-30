"""Supervise resumable translation/collection jobs and verify final coverage.

Only existing benign variants are submitted. Provider and model identities,
token ceilings, and reasoning settings come from run_benign_scenarios.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from run_benign_scenarios import (
    BENIGN, CONFIGS, LANGUAGES, OUTPUT_CAPS, OUT, ROOT, VARIANTS,
    matches_main_policy, now, read_csv, read_jsonl,
)
from watch_benign_scenarios import alive, refresh


def missing(config: str, conditions: list[str]) -> int:
    expected = {f"{s['prompt_id']}__{c}" for s in read_csv(BENIGN) for c in conditions}
    success = {
        r["variant_id"] for r in read_jsonl(OUT / f"{config}_raw.jsonl")
        if matches_main_policy(r, config, OUTPUT_CAPS[config])
        and r.get("request_status") == "success" and (r.get("response_text") or "").strip()
    }
    return len(expected - success)


def last_error(config: str, conditions: list[str]) -> str:
    rows = [r for r in read_jsonl(OUT / f"{config}_raw.jsonl") if r.get("condition_id") in conditions and matches_main_policy(r, config, OUTPUT_CAPS[config])]
    if not rows or rows[-1].get("request_status") == "success":
        return ""
    return rows[-1].get("error", "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-pid", type=int)
    parser.add_argument("--max-passes", type=int, default=3)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lock_path = OUT / "supervisor.lock"
    import fcntl
    lock = lock_path.open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another completion supervisor is already running.")

    tasks = []
    for config in CONFIGS:
        groups = [[c] for c, _, _ in LANGUAGES] if config.startswith("nvidia") else [[c for c, _, _ in LANGUAGES]]
        for conditions in groups:
            tasks.append({"name": config + "__" + "_".join(conditions), "config": config, "conditions": conditions, "passes": 0, "process": None, "retry_at": 0, "blocked_reason": ""})
    translator = None
    translator_log = None
    translation_passes = 0
    last_refresh = 0
    try:
        while True:
            current = time.time()
            external_translation = args.translation_pid and alive(args.translation_pid)
            translation_done = len(read_csv(VARIANTS)) == 280
            if translator is not None and translator.poll() is not None:
                translator_log.close()
                translator = None
            if not translation_done and not external_translation and translator is None and translation_passes < args.max_passes:
                translation_passes += 1
                translator_log = (OUT / "translation_resume.log").open("a", encoding="utf-8")
                translator = subprocess.Popen([sys.executable, "-u", "scripts/run_benign_scenarios.py", "translate"], cwd=ROOT, stdout=translator_log, stderr=subprocess.STDOUT)
                print(f"Translation pass {translation_passes} started", flush=True)

            for task in tasks:
                process = task["process"]
                if process is not None and process.poll() is not None:
                    task["log"].close()
                    task["process"] = None
                    remaining = missing(task["config"], task["conditions"])
                    if remaining:
                        error = last_error(task["config"], task["conditions"])
                        if any(term in error.lower() for term in ["401 client", "402 client", "403 client", "404 client", "request too large", "tokens per day", "requests per day", "tokens per day (tpd)"]):
                            task["blocked_reason"] = error
                        task["retry_at"] = current + 60
                        print(f"{task['name']} stopped with {remaining} remaining", flush=True)
                if task["process"] is None and not task["blocked_reason"] and task["passes"] < args.max_passes and current >= task["retry_at"] and missing(task["config"], task["conditions"]):
                    task["passes"] += 1
                    task["log"] = (OUT / (task["name"] + ".log")).open("a", encoding="utf-8")
                    task["log"].write(f"\nSupervisor pass {task['passes']} at {now()}\n")
                    task["log"].flush()
                    command = [sys.executable, "-u", "scripts/run_benign_scenarios.py", "collect", "--config", task["config"], "--conditions", *task["conditions"], "--follow-translations"]
                    task["process"] = subprocess.Popen(command, cwd=ROOT, stdout=task["log"], stderr=subprocess.STDOUT)
                    print(f"{task['name']} pass {task['passes']} started", flush=True)
                    time.sleep(2)

            running = [t["process"].pid for t in tasks if t["process"] is not None and t["process"].poll() is None]
            translation_pids = ([args.translation_pid] if external_translation else []) + ([translator.pid] if translator is not None and translator.poll() is None else [])
            if current - last_refresh >= 45:
                refresh(running + translation_pids)
                report = {
                    "updated_at_utc": now(),
                    "translation_complete": translation_done,
                    "tasks": [{"name": t["name"], "passes": t["passes"], "remaining": missing(t["config"], t["conditions"]), "running": t["process"] is not None and t["process"].poll() is None, "blocked_reason": t["blocked_reason"]} for t in tasks],
                }
                (OUT / "supervisor_status.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                last_refresh = current
            pending = any(missing(t["config"], t["conditions"]) for t in tasks)
            retryable = any(t["process"] is None and not t["blocked_reason"] and t["passes"] < args.max_passes and missing(t["config"], t["conditions"]) for t in tasks)
            if translation_done and not pending:
                break
            if not running and not translation_pids and not retryable:
                break
            time.sleep(10)
    except KeyboardInterrupt:
        print("Supervisor interrupted; child jobs may still run. Progress remains saved.", flush=True)
        raise
    refresh([])
    result = subprocess.run([sys.executable, "scripts/verify_benign_scenarios.py", "--require-complete"], cwd=ROOT)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
