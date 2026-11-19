"""Small, isolated benchmark of NVIDIA's free hosted prototype endpoints.

Reads existing study prompts unchanged. Never edits study checkpoints or selects
a replacement automatically. Saves responses and timing evidence as JSONL.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import threading
import time

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "nvidia/nemotron-3.5-bolt-e4b",
    "deepseek-ai/deepseek-v4.1-flash",
    "minimaxai/minimax-m3.1-flash",
)
ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


def request(model, prompt, timeout, max_tokens):
    started = time.perf_counter()
    record = {"model": model, "provider": "nvidia_free_prototype", "prompt_id": prompt["variant_id"],
              "language": prompt["language"], "prompt": prompt["prompt_text"],
              "prompt_sha256": hashlib.sha256(prompt["prompt_text"].encode()).hexdigest(),
              "max_tokens": max_tokens, "temperature": 0,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "error", "response": "", "reasoning_characters": 0,
              "first_content_seconds": None, "finish_reason": None, "usage": {}}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt["prompt_text"]}],
               "max_tokens": max_tokens, "temperature": 0, "stream": True}
    if model.startswith("nvidia/nemotron-3.5-bolt"):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    parts = []
    try:
        with requests.post(ENDPOINT, headers={"Authorization": "Bearer " + os.environ["NVIDIA_API_KEY"],
                                             "Accept": "text/event-stream"},
                           json=payload, stream=True, timeout=(10, timeout)) as response:
            record["http_status"] = response.status_code
            if response.status_code != 200:
                record["error"] = f"HTTP {response.status_code}"
                return record
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if time.perf_counter() - started > timeout:
                    record.update(status="timeout", error="Total request deadline exceeded")
                    break
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                chunk = json.loads(raw)
                if chunk.get("error"):
                    record["error"] = "Provider stream error"
                    break
                if chunk.get("usage"):
                    record["usage"] = chunk["usage"]
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        if record["first_content_seconds"] is None:
                            record["first_content_seconds"] = round(time.perf_counter() - started, 3)
                        parts.append(content)
                    record["reasoning_characters"] += len(delta.get("reasoning_content") or "")
                    if choice.get("finish_reason"):
                        record["finish_reason"] = choice["finish_reason"]
            if record["status"] != "timeout":
                record["status"] = ("success" if parts and record["finish_reason"] == "stop" else
                                    "truncated" if parts and record["finish_reason"] == "length" else "incomplete")
    except requests.RequestException as exc:
        record.update(status="timeout" if isinstance(exc, requests.Timeout) else "error",
                      error=type(exc).__name__)
    except (ValueError, TypeError, KeyError) as exc:
        record.update(status="error", error=type(exc).__name__)
    finally:
        record["response"] = "".join(parts)
        record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        record["response_characters"] = len(record["response"])
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--languages", nargs="+", default=["English", "Hindi", "Gujarati"])
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--max-tokens", type=int, default=1000)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not os.getenv("NVIDIA_API_KEY"):
        raise ValueError("NVIDIA_API_KEY is missing")
    source = ROOT / "dataset_fresh_start/data/translations/multilingual_prompts.csv"
    import csv
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    index = {r["language"]: r for r in rows
             if r["prompt_id"] == "MSF-001" and r["strategy"] == "persona_builder"}
    prompts = [index[language] for language in args.languages]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "responses.jsonl"
    if raw_path.exists():
        raise ValueError("Use a new benchmark output directory; existing results are preserved")
    metadata = {"models": MODELS, "languages": args.languages, "max_tokens": args.max_tokens,
                "temperature": 0, "timeout_seconds": args.timeout,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "free_access_reference": "https://docs.api.nvidia.com/nim/docs/product",
                "free_model_pages": ["https://build.nvidia.com/" + m for m in MODELS],
                "reasoning_settings": {"nvidia/nemotron-3.5-bolt-e4b": "enable_thinking=false; other models use provider defaults"},
                "notes": "Hosted free prototype endpoints only; no partner route, billing upgrade or paid fallback. One concurrent request per candidate. Existing background NVIDIA traffic may affect timings. No claim of production throughput or full-language quality validation."}
    (args.output_dir / "settings.json").write_text(json.dumps(metadata, indent=2) + "\n")
    lock, records = threading.Lock(), []

    def run(model):
        failures = 0
        for prompt in prompts:
            record = request(model, prompt, args.timeout, args.max_tokens)
            with lock:
                with raw_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                records.append(record)
                print(json.dumps({key: record.get(key) for key in (
                    "model", "language", "status", "http_status", "elapsed_seconds", "first_content_seconds",
                    "response_characters", "finish_reason", "error")}), flush=True)
            failures = 0 if record["status"] in ("success", "truncated") else failures + 1
            if failures >= 2:
                print(f"Stopping {model} benchmark after two consecutive failures; later languages untested", flush=True)
                break
            time.sleep(1)

    with ThreadPoolExecutor(max_workers=3) as executor:
        for future in as_completed([executor.submit(run, model) for model in MODELS]):
            future.result()
    summary = []
    for model in MODELS:
        tested = [r for r in records if r["model"] == model]
        usable = [r for r in tested if r["status"] in ("success", "truncated")]
        summary.append({"model": model, "attempted": len(tested), "planned": len(prompts),
                        "usable": len(usable), "complete": sum(r["status"] == "success" for r in tested),
                        "median_seconds_successes_only": statistics.median(r["elapsed_seconds"] for r in usable) if usable else None,
                        "median_first_content_seconds": statistics.median(r["first_content_seconds"] for r in usable) if usable else None})
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
