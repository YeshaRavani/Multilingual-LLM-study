"""Add translation provenance and create the four-prompt pilot/review files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from experiment import load_csv, write_csv


DEFAULT_PILOT_IDS = ("P001", "P002", "P005", "P006")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(__file__).resolve().parents[1] / path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="data/variants.csv")
    parser.add_argument("--source", default="data/source_prompts.csv")
    parser.add_argument("--pilot-output", default="data/pilot_variants.csv")
    parser.add_argument("--review-output", default="data/translation_review_template.csv")
    parser.add_argument("--pilot-ids", nargs="+", default=list(DEFAULT_PILOT_IDS))
    args = parser.parse_args()
    load_dotenv()

    variants_path = resolve_path(args.variants)
    rows = load_csv(variants_path)
    source = {row["prompt_id"]: row for row in load_csv(resolve_path(args.source))}
    backend = __import__("os").getenv("TRANSLATION_BACKEND", "nllb")
    model = __import__("os").getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    if backend == "indictrans2":
        model = __import__("os").getenv(
            "INDICTRANS2_MODEL", "ai4bharat/indictrans2-en-indic-dist-200M"
        )

    normalized = []
    for row in rows:
        method = row["generation_method"]
        row = {
            **row,
            "canonical_english_prompt": source[row["prompt_id"]]["canonical_english_prompt"],
            "translation_backend": backend if method == "machine_translate" else "",
            "generation_model": model if method == "machine_translate" else "",
        }
        if method == "machine_translate":
            row["status"] = "needs_translation_review"
        normalized.append(row)

    fields = [
        "variant_id", "prompt_id", "expected_outcome", "domain",
        "canonical_english_prompt", "condition_id", "condition_name",
        "generation_method", "translation_backend", "generation_model",
        "prompt_text", "status", "created_at_utc",
    ]
    write_csv(variants_path, normalized, fields)

    pilot_ids = set(args.pilot_ids)
    pilot = [row for row in normalized if row["prompt_id"] in pilot_ids]
    if len(pilot) != len(pilot_ids) * 10:
        raise RuntimeError(f"Expected {len(pilot_ids) * 10} pilot rows, found {len(pilot)}.")
    write_csv(resolve_path(args.pilot_output), pilot, fields)

    review_rows = []
    for row in normalized:
        if row["generation_method"] != "machine_translate":
            continue
        review_rows.append({
            "variant_id": row["variant_id"],
            "prompt_id": row["prompt_id"],
            "condition_name": row["condition_name"],
            "canonical_english_prompt": row["canonical_english_prompt"],
            "translated_prompt_text": row["prompt_text"],
            "meaning_preserved_yes_no": "",
            "risk_level_preserved_yes_no": "",
            "naturalness_1_to_5": "",
            "corrected_translation_if_needed": "",
            "reviewer_notes": "",
            "reviewer_name": "",
            "reviewed_at_utc": "",
        })
    write_csv(resolve_path(args.review_output), review_rows, list(review_rows[0]))
    print(
        f"Prepared {len(normalized)} full variants, {len(pilot)} pilot variants, "
        f"and {len(review_rows)} translation-review rows."
    )


if __name__ == "__main__":
    main()
