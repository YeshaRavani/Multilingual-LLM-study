"""Apply human translation/style review and emit API-ready variant files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from experiment import load_csv, write_csv


YES_VALUES = {"yes", "y", "true", "1"}


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(__file__).resolve().parents[1] / path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="data/variants.csv")
    parser.add_argument("--translation-reviews", default="data/translation_review_template.csv")
    parser.add_argument("--manual-styles", default="data/manual_style_variants.csv")
    parser.add_argument("--output", default="data/variants_reviewed.csv")
    parser.add_argument("--pilot-output", default="data/pilot_variants_reviewed.csv")
    parser.add_argument("--pilot-ids", nargs="+", default=["P001", "P002", "P005", "P006"])
    args = parser.parse_args()

    variants = load_csv(resolve_path(args.variants))
    reviews = {
        row["variant_id"]: row for row in load_csv(resolve_path(args.translation_reviews))
    }
    manual_path = resolve_path(args.manual_styles)
    manual = {
        (row["prompt_id"], row["condition_id"]): row.get("prompt_text", "").strip()
        for row in load_csv(manual_path)
    } if manual_path.exists() else {}

    unresolved = []
    for row in variants:
        if row["generation_method"] == "machine_translate":
            review = reviews.get(row["variant_id"], {})
            meaning_ok = review.get("meaning_preserved_yes_no", "").strip().lower() in YES_VALUES
            risk_ok = review.get("risk_level_preserved_yes_no", "").strip().lower() in YES_VALUES
            corrected = review.get("corrected_translation_if_needed", "").strip()
            if meaning_ok and risk_ok:
                if corrected:
                    row["prompt_text"] = corrected
                row["status"] = "ready"
            else:
                unresolved.append(row["variant_id"])
        elif row["generation_method"] == "manual":
            prompt_text = manual.get((row["prompt_id"], row["condition_id"]), "")
            if prompt_text:
                row["prompt_text"] = prompt_text
                row["status"] = "ready"
            else:
                unresolved.append(row["variant_id"])

    fields = list(variants[0])
    write_csv(resolve_path(args.output), variants, fields)
    pilot_ids = set(args.pilot_ids)
    pilot = [row for row in variants if row["prompt_id"] in pilot_ids]
    write_csv(resolve_path(args.pilot_output), pilot, fields)

    if unresolved:
        print(f"Review incomplete: {len(unresolved)} variants are not ready.")
        print("First unresolved IDs: " + ", ".join(unresolved[:10]))
        raise SystemExit(2)
    print(f"All {len(variants)} variants are ready; pilot contains {len(pilot)} rows.")


if __name__ == "__main__":
    main()
