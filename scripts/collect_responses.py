"""Call the selected model APIs and write raw results as JSON Lines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from experiment import append_jsonl, call_gemini, call_groq, call_llama, call_openai, call_openrouter, load_csv, now_utc, sleep_briefly

CALLERS = {
    "openai": call_openai,
    "gemini": call_gemini,
    "llama": call_llama,
    "groq": call_groq,
    "openrouter": call_openrouter,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", nargs="+", choices=CALLERS, default=list(CALLERS))
    parser.add_argument("--variants", default="data/variants.csv")
    parser.add_argument("--output", default="outputs/responses.jsonl")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    variants_path = Path(args.variants)
    if not variants_path.is_absolute():
        variants_path = Path(__file__).resolve().parents[1] / variants_path
    variants = load_csv(variants_path)
    incomplete = [row for row in variants if row["status"] != "ready"]
    if incomplete:
        raise RuntimeError(
            f"{len(incomplete)} variants are not approved. Complete translation review "
            "and manual style entries, then run scripts/apply_reviews.py."
        )
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parents[1] / output_path
    total = len(variants) * len(args.providers)
    print(f"Preparing {total} API calls.")

    for provider in args.providers:
        caller = CALLERS[provider]
        for variant in variants:
            if args.dry_run:
                print(f"{provider}: {variant['variant_id']}")
                continue
            record = {"run_at_utc": now_utc(), "provider": provider, **variant}
            try:
                response_text, metadata = caller(variant["prompt_text"])
                record.update(metadata)
                record.update({"response_text": response_text, "request_status": "success", "error": None})
            except Exception as error:  # retain failed calls for transparent reruns
                record.update({"response_text": None, "request_status": "error", "error": str(error)})
            append_jsonl(output_path, record)
            print(f"{provider}: {variant['variant_id']}  {record['request_status']}")
            sleep_briefly(provider)


if __name__ == "__main__":
    main()
