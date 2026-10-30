"""Call the selected model APIs and write raw results as JSON Lines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from experiment import append_jsonl, call_gemini, call_groq, call_llama, call_nvidia, call_openai, call_openrouter, load_csv, now_utc, require_env, sleep_briefly

CALLERS = {
    "openai": call_openai,
    "gemini": call_gemini,
    "llama": call_llama,
    "groq": call_groq,
    "nvidia": call_nvidia,
    "openrouter": call_openrouter,
}

PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
    "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL"),
    "llama": ("LLAMA_API_KEY", "LLAMA_MODEL", "LLAMA_BASE_URL"),
    "groq": ("GROQ_API_KEY", "GROQ_MODEL", "GROQ_BASE_URL"),
    "nvidia": ("NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_BASE_URL"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", nargs="+", choices=CALLERS, default=list(CALLERS))
    parser.add_argument("--variants", default="data/variants.csv")
    parser.add_argument("--output", default="outputs/responses.jsonl")
    parser.add_argument("--conditions", nargs="+", help="Only collect the listed condition IDs")
    parser.add_argument("--prompt-ids", nargs="+", help="Only collect the listed source prompt IDs")
    parser.add_argument("--variant-ids", nargs="+", help="Only collect the listed exact variant IDs")
    parser.add_argument("--run-label", default="", help="Optional provenance label stored with every response")
    parser.add_argument(
        "--allow-unreviewed-translations",
        action="store_true",
        help="Preliminary runs only: allow rows marked needs_translation_review",
    )
    parser.add_argument("--resume", action="store_true", help="Skip provider/variant pairs already successful in the output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    if not args.dry_run:
        for provider in args.providers:
            for variable in PROVIDER_ENV[provider]:
                require_env(variable)
    variants_path = Path(args.variants)
    if not variants_path.is_absolute():
        variants_path = Path(__file__).resolve().parents[1] / variants_path
    variants = load_csv(variants_path)
    if args.variant_ids:
        requested_variants = set(args.variant_ids)
        variants = [row for row in variants if row["variant_id"] in requested_variants]
        found_variants = {row["variant_id"] for row in variants}
        missing_variants = requested_variants - found_variants
        if missing_variants:
            raise RuntimeError("Unknown or absent variant IDs: " + ", ".join(sorted(missing_variants)))
    if args.prompt_ids:
        requested_prompts = set(args.prompt_ids)
        variants = [row for row in variants if row["prompt_id"] in requested_prompts]
        found_prompts = {row["prompt_id"] for row in variants}
        missing_prompts = requested_prompts - found_prompts
        if missing_prompts:
            raise RuntimeError("Unknown or absent prompt IDs: " + ", ".join(sorted(missing_prompts)))
    if args.conditions:
        requested_conditions = set(args.conditions)
        variants = [row for row in variants if row["condition_id"] in requested_conditions]
        found_conditions = {row["condition_id"] for row in variants}
        missing_conditions = requested_conditions - found_conditions
        if missing_conditions:
            raise RuntimeError("Unknown or absent conditions: " + ", ".join(sorted(missing_conditions)))

    allowed_statuses = {"ready"}
    if args.allow_unreviewed_translations:
        allowed_statuses.add("needs_translation_review")
    incomplete = [row for row in variants if row["status"] not in allowed_statuses]
    if incomplete:
        raise RuntimeError(
            f"{len(incomplete)} variants are not approved. Complete translation review "
            "and manual style entries, then run scripts/apply_reviews.py."
        )
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parents[1] / output_path
    completed: set[tuple[str, str]] = set()
    if args.resume and output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("request_status") == "success" and (record.get("response_text") or "").strip():
                completed.add((record.get("provider", ""), record.get("variant_id", "")))

    jobs = [
        (provider, variant)
        for provider in args.providers
        for variant in variants
        if (provider, variant["variant_id"]) not in completed
    ]
    total = len(jobs)
    print(f"Preparing {total} API calls.")

    for provider, variant in jobs:
        caller = CALLERS[provider]
        if args.dry_run:
            print(f"{provider}: {variant['variant_id']}")
            continue
        record = {
            "run_at_utc": now_utc(),
            "provider": provider,
            "run_label": args.run_label,
            "configured_max_output_tokens": int(require_env("MAX_OUTPUT_TOKENS")),
            "study_stage": (
                "preliminary_unreviewed_translation"
                if variant["status"] == "needs_translation_review"
                else "preliminary"
            ),
            **variant,
        }
        try:
            response_text, metadata = caller(variant["prompt_text"])
            record.update(metadata)
            record.update(
                {
                    "response_text": response_text,
                    "request_status": "success" if (response_text or "").strip() else "empty",
                    "error": None if (response_text or "").strip() else "No visible response text returned.",
                }
            )
        except Exception as error:  # retain failed calls for transparent reruns
            record.update({"response_text": None, "request_status": "error", "error": str(error)})
        append_jsonl(output_path, record)
        print(f"{provider}: {variant['variant_id']}  {record['request_status']}")
        sleep_briefly(provider)


if __name__ == "__main__":
    main()
