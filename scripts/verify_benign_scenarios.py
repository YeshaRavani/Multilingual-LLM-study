"""Check source provenance, translation coverage, and collected response coverage."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from run_benign_scenarios import (
    BENIGN, CONFIGS, LANGUAGES, OUTPUT_CAPS, OUT, VARIANTS,
    digest, export_results, matches_main_policy, now, read_csv, read_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    source = {r["prompt_id"]: r for r in read_csv(BENIGN)}
    variants = read_csv(VARIANTS)
    assert len(source) == 40
    assert len({r["variant_id"] for r in variants}) == len(variants)
    expected_variants = {f"{p}__{c}" for p in source for c, _, _ in LANGUAGES}
    assert {r["variant_id"] for r in variants} <= expected_variants
    for row in variants:
        original = source[row["prompt_id"]]
        assert row["canonical_english_prompt"] == original["canonical_english_prompt"]
        assert row["source_prompt_sha256"] == digest(original["canonical_english_prompt"])
        assert row["expected_outcome"] == "answer" and row["prompt_text"].strip()
        assert row["translation_truncated"] == "no"
        if row["condition_id"] == "standard_english":
            assert row["prompt_text"] == original["canonical_english_prompt"]
        else:
            assert row["status"] == "needs_translation_review"
    export_results()
    combined = read_csv(OUT / "all_models_consolidated.csv")
    assert len(combined) == 840
    assert len({(r["configuration"], r["variant_id"]) for r in combined}) == 840
    successful = 0
    missing = []
    config_counts = {}
    for config in CONFIGS:
        attempts = read_jsonl(OUT / f"{config}_raw.jsonl")
        group = [r for r in combined if r["configuration"] == config]
        assert len(group) == 280
        for row in group:
            if row["collection_status"] == "complete":
                assert row["response_text"].strip()
                candidates = [r for r in attempts if r["variant_id"] == row["variant_id"] and matches_main_policy(r, config, OUTPUT_CAPS[config]) and r.get("request_status") == "success" and (r.get("response_text") or "").strip()]
                assert candidates
                selected = candidates[-1]
                assert selected["prompt_text"] == row["prompt_text"]
                assert selected["response_text"] == row["response_text"]
                assert selected["model"] == row["model"]
                successful += 1
            else:
                missing.append({"configuration": config, "variant_id": row["variant_id"], "status": row["collection_status"]})
            assert not row["benign_assistance_score"]
        config_counts[config] = dict(Counter(r["collection_status"] for r in group))
    report = {
        "verified_at_utc": now(),
        "integrity_checks": "passed",
        "translation_variants_expected": 280,
        "translation_variants_present": len(variants),
        "translation_human_review": "pending",
        "responses_expected": 840,
        "responses_collected": successful,
        "all_collection_complete": len(variants) == 280 and successful == 840,
        "configurations": config_counts,
        "missing_responses": missing,
    }
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "missing_responses"}, indent=2))
    if args.require_complete and not report["all_collection_complete"]:
        raise SystemExit("Collection is not yet complete; see verification.json for exact missing rows.")


if __name__ == "__main__":
    main()
