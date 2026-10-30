"""Split, translate, collect, and export the benign narrative experiment.

Every stage checkpoints to separate files and can resume. No harmful prompts
are submitted by this pipeline. Scores remain blank pending human annotation.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SOURCE = ROOT / "data/source_prompts_research_scenarios_v2.csv"
BENIGN = ROOT / "data/source_prompts_research_scenarios_v2_benign.csv"
HARMFUL = ROOT / "data/source_prompts_research_scenarios_v2_harmful.csv"
VARIANTS = ROOT / "data/benign_scenario_variants_v2.csv"
OUT = ROOT / "outputs/benign_scenarios_v2"
LANGUAGES = [
    ("standard_english", "Standard English", "eng_Latn"),
    ("hindi", "Hindi", "hin_Deva"),
    ("gujarati", "Gujarati", "guj_Gujr"),
    ("punjabi", "Punjabi", "pan_Guru"),
    ("bengali", "Bengali", "ben_Beng"),
    ("marathi", "Marathi", "mar_Deva"),
    ("kannada", "Kannada", "kan_Knda"),
]
CONFIGS = {
    "nvidia_gpt_oss_20b": ("nvidia", "openai/gpt-oss-20b", "NVIDIA_API_KEY", "NVIDIA_BASE_URL"),
    "groq_gpt_oss_20b": ("groq", "openai/gpt-oss-20b", "GROQ_API_KEY", "GROQ_BASE_URL"),
    "groq_qwen_3_8_27b": ("groq", "qwen/qwen3.8-27b", "GROQ_API_KEY", "GROQ_BASE_URL"),
}
OUTPUT_CAPS = {"nvidia_gpt_oss_20b": 1200, "groq_gpt_oss_20b": 1200, "groq_qwen_3_8_27b": 1000}


def matches_main_policy(record: dict, config: str, cap: int) -> bool:
    return record.get("configured_max_output_tokens") == cap and (
        config != "nvidia_gpt_oss_20b" or record.get("reasoning_effort") == "low"
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        lines = handle.read().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def prepare() -> None:
    rows = read_csv(SOURCE)
    benign = [r for r in rows if r["expected_outcome"] == "answer"]
    harmful = [r for r in rows if r["expected_outcome"] == "refusal"]
    assert len(benign) == 40 and len(harmful) == 20
    assert len({r["prompt_id"] for r in rows}) == 60
    write_csv(BENIGN, benign)
    write_csv(HARMFUL, harmful)
    print("Separated 40 benign scenarios and 20 harmful controls.", flush=True)


def translate(batch_size: int) -> None:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    torch.set_num_threads(min(8, os.cpu_count() or 4))
    model_id = "facebook/nllb-200-distilled-600M"
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_id, src_lang="eng_Latn", local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, local_files_only=True).to(device)
    model.eval()
    print(f"Translation device: {device}", flush=True)
    sources = read_csv(BENIGN)
    assert len(sources) == 40 and all(r["expected_outcome"] == "answer" for r in sources)
    lookup = {r["variant_id"]: r for r in read_csv(VARIANTS)} if VARIANTS.exists() else {}
    checkpoint = OUT / "translation_checkpoint.jsonl"
    for row in read_jsonl(checkpoint):
        lookup[row["variant_id"]] = row

    for condition, name, code in LANGUAGES:
        pending = []
        for source in sources:
            key = f"{source['prompt_id']}__{condition}"
            if key in lookup:
                assert lookup[key]["source_prompt_sha256"] == digest(source["canonical_english_prompt"])
                continue
            pending.append(source)
        print(f"{name}: {len(pending)} variants remaining", flush=True)
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset:offset + batch_size]
            texts = [r["canonical_english_prompt"] for r in batch]
            input_counts = [len(tokenizer(t)["input_ids"]) for t in texts]
            if max(input_counts) > 512:
                raise RuntimeError(f"{name}: input exceeds 512 tokens; no silent truncation allowed")
            if condition == "standard_english":
                outputs = texts
                output_counts = input_counts
            else:
                inputs = tokenizer(texts, padding=True, truncation=False, return_tensors="pt").to(device)
                with torch.inference_mode():
                    generated = model.generate(
                        **inputs,
                        forced_bos_token_id=tokenizer.convert_tokens_to_ids(code),
                        max_new_tokens=768,
                        num_beams=3,
                    )
                # Encoder-decoder models include EOS as the initial decoder token.
                for sequence in generated:
                    if not (sequence[1:] == tokenizer.eos_token_id).any().item():
                        raise RuntimeError(f"{name}: translation hit output limit; refusing to save partial text")
                outputs = tokenizer.batch_decode(generated, skip_special_tokens=True)
                output_counts = [int((seq != tokenizer.pad_token_id).sum().item()) for seq in generated]
            for source, text, input_count, output_count in zip(batch, outputs, input_counts, output_counts):
                if not text.strip():
                    raise RuntimeError(f"Empty translation for {source['prompt_id']}/{condition}")
                row = {
                    **source,
                    "variant_id": f"{source['prompt_id']}__{condition}",
                    "condition_id": condition,
                    "condition_name": name,
                    "domain": source["category"],
                    "generation_method": "canonical" if condition == "standard_english" else "machine_translate",
                    "translation_backend": "" if condition == "standard_english" else "nllb",
                    "generation_model": "" if condition == "standard_english" else model_id,
                    "prompt_text": text,
                    "status": "ready" if condition == "standard_english" else "needs_translation_review",
                    "source_prompt_sha256": digest(source["canonical_english_prompt"]),
                    "translation_input_tokens": str(input_count),
                    "translation_output_tokens": str(output_count),
                    "translation_truncated": "no",
                    "created_at_utc": now(),
                }
                append(checkpoint, row)
                lookup[row["variant_id"]] = row
            ordered = [lookup[f"{r['prompt_id']}__{c}"] for r in sources for c, _, _ in LANGUAGES if f"{r['prompt_id']}__{c}" in lookup]
            write_csv(VARIANTS, ordered)
            print(f"{name}: {min(offset + batch_size, len(pending))}/{len(pending)} translated; {len(ordered)}/280 total", flush=True)
    assert len(lookup) == 280
    print("Translation complete: 280 variants, including 40 canonical English.", flush=True)


def collect(config: str, limit: int | None, cap: int, available_only: bool = False, conditions: list[str] | None = None) -> bool:
    from dotenv import load_dotenv
    from experiment import call_openai_compatible

    load_dotenv(ROOT / ".env")
    provider, model_id, key_env, base_env = CONFIGS[config]
    os.environ["SCENARIO_MODEL"] = model_id
    os.environ["MAX_OUTPUT_TOKENS"] = str(cap)
    os.environ["TEMPERATURE"] = "0"
    os.environ["NVIDIA_REASONING_EFFORT"] = "low"
    for key in (key_env, base_env):
        if not os.getenv(key):
            raise RuntimeError(f"Missing {key}")
    variants = read_csv(VARIANTS)
    assert len(variants) == 280 or available_only or (limit is not None and len(variants) >= limit)
    assert all(r["expected_outcome"] == "answer" for r in variants)
    if conditions:
        variants = [v for v in variants if v["condition_id"] in conditions]
    path = OUT / f"{config}_raw.jsonl"
    successful = {r["variant_id"]: r for r in read_jsonl(path) if matches_main_policy(r, config, cap) and r.get("request_status") == "success" and r.get("response_text", "").strip()}
    for v in variants:
        if v["variant_id"] in successful:
            old = successful[v["variant_id"]]
            assert old["prompt_text"] == v["prompt_text"] and old["model"] == model_id
    pending = [v for v in variants if v["variant_id"] not in successful]
    if limit is not None:
        pending = pending[:limit]
    errors = 0
    print(f"{config}: {len(successful)}/280 already successful; {len(pending)} calls planned", flush=True)
    for index, variant in enumerate(pending, 1):
        record = {
            **variant,
            "run_at_utc": now(),
            "provider": provider,
            "model": model_id,
            "run_label": "benign_scenarios_v2_language_only",
            "study_stage": "preliminary_unreviewed_scenarios_and_translations",
            "configured_max_output_tokens": cap,
            "temperature": 0,
            "reasoning_effort": "none" if model_id.startswith("qwen/") else "low",
        }
        stop = False
        try:
            text, metadata = call_openai_compatible(
                variant["prompt_text"], provider=provider,
                api_key_env=key_env, model_env="SCENARIO_MODEL", base_url_env=base_env,
            )
            record.update(metadata)
            record["response_text"] = text or ""
            record["request_status"] = "success" if (text or "").strip() else "empty"
            record["error"] = "" if record["request_status"] == "success" else "No visible response text"
            errors = 0 if record["request_status"] == "success" else errors + 1
        except Exception as error:
            response = getattr(error, "response", None)
            status = getattr(response, "status_code", None)
            message = str(error)
            if response is not None:
                message += " " + response.text[:2000]
            for secret_key in ("GROQ_API_KEY", "NVIDIA_API_KEY", "HUGGINGFACE_TOKEN", "HF_TOKEN"):
                secret = os.getenv(secret_key)
                if secret:
                    message = message.replace(secret, "[REDACTED]")
            record.update(response_text="", request_status="error", error=message, http_status=status)
            errors += 1
            stop = status in {400, 401, 402, 403, 404, 429}
        append(path, record)
        print(f"{config} {index}/{len(pending)} {variant['variant_id']} {record['request_status']} finish={record.get('finish_reason')}", flush=True)
        if stop or errors >= 3:
            print(f"{config}: paused after provider error or repeated empty/error responses; saved all attempts", flush=True)
            return False
        time.sleep(10 if provider == "groq" else 1.5)
    return True


def export_results(cap: int | None = None) -> None:
    available = {v["variant_id"]: v for v in read_csv(VARIANTS)}
    variants = []
    for source in read_csv(BENIGN):
        english = available[f"{source['prompt_id']}__standard_english"]
        for condition, name, _ in LANGUAGES:
            key = f"{source['prompt_id']}__{condition}"
            variants.append(available.get(key) or {
                **english, "variant_id": key, "condition_id": condition,
                "condition_name": name, "generation_method": "machine_translate",
                "translation_backend": "nllb", "generation_model": "facebook/nllb-200-distilled-600M",
                "prompt_text": "", "status": "translation_pending",
                "translation_input_tokens": "", "translation_output_tokens": "",
                "translation_truncated": "", "created_at_utc": "",
            })
    all_rows, summary = [], []
    for config, (provider, model_id, _, _) in CONFIGS.items():
        selected_cap = cap if cap is not None else OUTPUT_CAPS[config]
        attempts = read_jsonl(OUT / f"{config}_raw.jsonl")
        rows = []
        for variant in variants:
            matching = [r for r in attempts if r["variant_id"] == variant["variant_id"] and matches_main_policy(r, config, selected_cap)]
            valid = [r for r in matching if r.get("request_status") == "success" and r.get("response_text", "").strip()]
            selected = valid[-1] if valid else (matching[-1] if matching else {})
            usage = selected.get("usage") or {}
            text = selected.get("response_text") or ""
            row = {
                **variant,
                "configuration": config, "provider": provider, "model": model_id,
                "collection_status": "complete" if valid else (selected.get("request_status") or ("translation_pending" if variant["status"] == "translation_pending" else "not_attempted")),
                "attempt_count": len(matching),
                "selected_run_at_utc": selected.get("run_at_utc", ""),
                "configured_max_output_tokens": selected.get("configured_max_output_tokens", ""),
                "reasoning_effort": selected.get("reasoning_effort", "none" if model_id.startswith("qwen/") else "low"),
                "finish_reason": selected.get("finish_reason", ""),
                "prompt_tokens": usage.get("prompt_tokens", ""),
                "completion_tokens": usage.get("completion_tokens", ""),
                "total_tokens": usage.get("total_tokens", ""),
                "response_text": text,
                "output_completeness": "potentially_truncated" if selected.get("finish_reason") == "length" else ("needs_review" if text else "unscorable"),
                "error": selected.get("error", ""),
                "annotation_status": "pending_human_review" if text else "unscorable",
                "benign_assistance_score": "",
                "language_adherence_score": "",
                "factual_quality_score": "",
                "completeness_score": "",
                "annotation_rationale": "",
            }
            rows.append(row)
        write_csv(OUT / f"{config}_consolidated.csv", rows)
        all_rows.extend(rows)
        for condition, name, _ in LANGUAGES:
            group = [r for r in rows if r["condition_id"] == condition]
            counts = Counter(r["collection_status"] for r in group)
            summary.append({
                "configuration": config, "condition_name": name, "expected_rows": len(group),
                "complete": counts["complete"], "empty": counts["empty"],
                "error": counts["error"], "not_attempted": counts["not_attempted"],
                "translation_pending": counts["translation_pending"],
                "potentially_truncated": sum(r["finish_reason"] == "length" for r in group),
            })
    write_csv(OUT / "all_models_consolidated.csv", all_rows)
    write_csv(OUT / "collection_summary.csv", summary)
    print(json.dumps(dict(Counter(r["collection_status"] for r in all_rows))), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "translate", "collect", "export"])
    parser.add_argument("--config", choices=CONFIGS)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-output-tokens", type=int, default=None, help="Override the configuration-specific default token ceiling")
    parser.add_argument("--follow-translations", action="store_true", help="Collect available variants while translation checkpoints grow")
    parser.add_argument("--conditions", nargs="+", choices=[c for c, _, _ in LANGUAGES], help="Restrict to disjoint language groups for provider-safe parallel runs")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == "prepare":
        prepare()
    elif args.stage == "translate":
        translate(args.batch_size)
    elif args.stage == "collect":
        if not args.config:
            parser.error("collect requires --config")
        while True:
            selected_cap = args.max_output_tokens if args.max_output_tokens is not None else OUTPUT_CAPS[args.config]
            continuing = collect(args.config, args.limit, selected_cap, args.follow_translations, args.conditions)
            if not continuing or not args.follow_translations or args.limit is not None:
                break
            if len(read_csv(VARIANTS)) == 280:
                # A final pass includes translations that appeared during the last pass.
                collect(args.config, None, selected_cap, conditions=args.conditions)
                break
            print(f"{args.config}: waiting for more translation checkpoints", flush=True)
            time.sleep(30)
    else:
        export_results(args.max_output_tokens)


if __name__ == "__main__":
    main()
