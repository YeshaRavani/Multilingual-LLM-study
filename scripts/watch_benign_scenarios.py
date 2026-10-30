"""Refresh result snapshots while explicitly identified experiment jobs run."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import Counter

from run_benign_scenarios import CONFIGS, OUTPUT_CAPS, OUT, VARIANTS, export_results, now, read_csv


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def refresh(pids: list[int]) -> bool:
    export_results()
    rows = read_csv(OUT / "all_models_consolidated.csv")
    variants = read_csv(VARIANTS)
    active = [pid for pid in pids if alive(pid)]
    counts = Counter(r["collection_status"] for r in rows)
    summary = {
        "updated_at_utc": now(),
        "main_output_token_caps": OUTPUT_CAPS,
        "translation_variants_available": len(variants),
        "translation_variants_expected": 280,
        "translation_languages": dict(Counter(v["condition_name"] for v in variants)),
        "responses_expected": 840,
        "response_status_counts": dict(counts),
        "active_process_ids": active,
        "state": "running" if active else ("complete" if counts["complete"] == 840 else "partial_or_paused"),
        "configurations": {
            name: dict(Counter(r["collection_status"] for r in rows if r["configuration"] == name))
            for name in CONFIGS
        },
    }
    temporary = OUT / "progress.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUT / "progress.json")
    lines = [
        "# Current experiment progress", "",
        f"Updated (UTC): {summary['updated_at_utc']}",
        f"State: {summary['state']}",
        f"Prompt variants available: {len(variants)}/280.",
        f"Responses collected under the documented model settings: {counts['complete']}/840.", "",
        "| Configuration | Saved responses | Errors | Empty | Not attempted | Awaiting translation |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, count in summary["configurations"].items():
        lines.append(f"| {name} | {count.get('complete', 0)} | {count.get('error', 0)} | {count.get('empty', 0)} | {count.get('not_attempted', 0)} | {count.get('translation_pending', 0)} |")
    lines.extend(["", "Counts refer to collected text, not verified answer quality. Quality scores await human review."])
    if not active and counts["complete"] < 840:
        lines.extend(["", "Jobs have stopped with unfinished rows. Inspect the raw attempt logs for provider/quota errors and resume only the affected configurations."])
    (OUT / "CURRENT_STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"state": summary["state"], "variants": len(variants), "responses": counts["complete"], "active_jobs": len(active)}), flush=True)
    return bool(active)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pids", nargs="+", type=int, required=True)
    args = parser.parse_args()
    while True:
        try:
            if not refresh(args.pids):
                break
        except (json.JSONDecodeError, csv.Error) as error:
            print(f"Snapshot deferred during concurrent write: {type(error).__name__}", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
