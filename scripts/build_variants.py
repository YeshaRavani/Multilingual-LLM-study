"""Create all 10 prompt conditions from the canonical English source dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(__import__('pathlib').Path(__file__).resolve().parents[1] / "src"))
from experiment import (
    CONDITIONS,
    create_translator,
    load_csv,
    now_utc,
    translate_batch,
    write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/source_prompts.csv", help="Canonical English prompt CSV")
    parser.add_argument("--output", default="data/variants.csv", help="Generated variant CSV")
    parser.add_argument("--manual-file", default="data/manual_style_variants.csv", help="Completed manual style variants")
    parser.add_argument("--manual-template", default="data/manual_style_variants_template.csv", help="Template for missing manual style variants")
    args = parser.parse_args()
    load_dotenv()
    source_path = Path(args.source)
    if not source_path.is_absolute():
        source_path = Path(__file__).resolve().parents[1] / source_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parents[1] / output_path
    manual_path = Path(args.manual_file)
    if not manual_path.is_absolute():
        manual_path = Path(__file__).resolve().parents[1] / manual_path
    manual_template_path = Path(args.manual_template)
    if not manual_template_path.is_absolute():
        manual_template_path = Path(__file__).resolve().parents[1] / manual_template_path
    source = load_csv(source_path)
    manual_rows = load_csv(manual_path) if manual_path.exists() else []
    manual_lookup = {(row["prompt_id"], row["condition_id"]): row.get("prompt_text", "") for row in manual_rows}
    backend = __import__("os").getenv("TRANSLATION_BACKEND", "indictrans2").strip().lower()
    translator = create_translator(backend)
    translated: dict[tuple[str, str], str] = {}

    machine_conditions = [condition for condition in CONDITIONS if condition[3] == "machine_translate"]
    source_texts = [item["canonical_english_prompt"] for item in source]
    for condition_id, condition_name, language_code, _ in machine_conditions:
        print(f"Translating {len(source_texts)} prompts into {condition_name}...")
        outputs = translate_batch(source_texts, language_code, backend, translator)
        if len(outputs) != len(source):
            raise RuntimeError(
                f"{condition_name} translation returned {len(outputs)} rows for {len(source)} prompts."
            )
        for item, prompt_text in zip(source, outputs):
            translated[(item["prompt_id"], condition_id)] = prompt_text

    variants, manual_template = [], []

    for item in source:
        for condition_id, condition_name, language_code, method in CONDITIONS:
            prompt_text, status = "", "ready"
            if method == "canonical":
                prompt_text = item["canonical_english_prompt"]
            elif method == "machine_translate":
                prompt_text = translated[(item["prompt_id"], condition_id)]
                status = "needs_translation_review"
            else:
                prompt_text = manual_lookup.get((item["prompt_id"], condition_id), "")
                if not prompt_text.strip():
                    status = "needs_manual_entry"
                    manual_template.append({"prompt_id": item["prompt_id"], "condition_id": condition_id, "condition_name": condition_name, "canonical_english_prompt": item["canonical_english_prompt"], "prompt_text": ""})
            variants.append({
                "variant_id": f"{item['prompt_id']}__{condition_id}", "prompt_id": item["prompt_id"],
                "expected_outcome": item["expected_outcome"], "domain": item["domain"],
                "canonical_english_prompt": item["canonical_english_prompt"],
                "condition_id": condition_id, "condition_name": condition_name, "generation_method": method,
                "translation_backend": backend if method == "machine_translate" else "",
                "generation_model": (
                    getattr(translator, "model_name", "google-translate-v2")
                    if method == "machine_translate" else ""
                ),
                "prompt_text": prompt_text, "status": status, "created_at_utc": now_utc(),
            })

    fields = list(variants[0])
    write_csv(output_path, variants, fields)
    if manual_template:
        write_csv(manual_template_path, manual_template, list(manual_template[0]))
        print(f"Created {len(variants)} variants. Fill {manual_path} using {manual_template_path}, then run this command again.")
    else:
        print(f"Created {len(variants)} ready variants in {output_path}.")


if __name__ == "__main__":
    main()
