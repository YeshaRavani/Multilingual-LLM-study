"""Shared helpers for the multilingual LLM safety-fairness pilot."""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"

CONDITIONS = [
    ("standard_english", "Standard English", None, "canonical"),
    ("indian_english", "Indian English", None, "manual"),
    ("informal_english", "Informal English", None, "manual"),
    ("hindi", "Hindi", "hi", "machine_translate"),
    ("hinglish", "Hinglish", None, "manual"),
    ("gujarati", "Gujarati", "gu", "machine_translate"),
    ("punjabi", "Punjabi", "pa", "machine_translate"),
    ("bengali", "Bengali", "bn", "machine_translate"),
    ("marathi", "Marathi", "mr", "machine_translate"),
    ("kannada", "Kannada", "kn", "machine_translate"),
]

INDICTRANS_LANGUAGE_CODES = {
    "hi": "hin_Deva",
    "gu": "guj_Gujr",
    "pa": "pan_Guru",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "kn": "kan_Knda",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def translate_google(text: str, target_language: str, api_key: str) -> str:
    response = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        params={"key": api_key},
        json={"q": text, "target": target_language, "format": "text"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["data"]["translations"][0]["translatedText"]


class IndicTrans2Translator:
    """Lazy-loaded English-to-Indic translator for local, batched inference."""

    def __init__(self) -> None:
        try:
            import torch
            from IndicTransToolkit import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "IndicTrans2 dependencies are missing. Run `pip install -r requirements.txt`."
            ) from exc

        model_name = os.getenv(
            "INDICTRANS2_MODEL", "ai4bharat/indictrans2-en-indic-dist-200M"
        )
        token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("Missing HUGGINGFACE_TOKEN. Add it to .env before translating.")

        if torch.cuda.is_available():
            self.device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        self.torch = torch
        self.processor = IndicProcessor(inference=True)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True, token=token
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, trust_remote_code=True, token=token
        ).to(self.device)
        self.model.eval()
        self.model_name = model_name

    def translate_batch(self, texts: list[str], target_language: str) -> list[str]:
        if target_language not in INDICTRANS_LANGUAGE_CODES:
            raise ValueError(f"Unsupported IndicTrans2 target language: {target_language}")
        target_code = INDICTRANS_LANGUAGE_CODES[target_language]
        prepared = self.processor.preprocess_batch(
            texts,
            src_lang="eng_Latn",
            tgt_lang=target_code,
            visualize=False,
        )
        inputs = self.tokenizer(
            prepared,
            padding="longest",
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                use_cache=True,
                min_length=0,
                max_length=512,
                num_beams=5,
                num_return_sequences=1,
            )
        decoded = self.tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        return self.processor.postprocess_batch(decoded, lang=target_code)


class NLLBTranslator:
    """Ungated local fallback covering the six native-script conditions."""

    def __init__(self) -> None:
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "NLLB dependencies are missing. Run `pip install -r requirements.txt`."
            ) from exc

        model_name = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
        if torch.cuda.is_available():
            self.device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, src_lang="eng_Latn")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self.model_name = model_name

    def translate_batch(self, texts: list[str], target_language: str) -> list[str]:
        if target_language not in INDICTRANS_LANGUAGE_CODES:
            raise ValueError(f"Unsupported NLLB target language: {target_language}")
        target_code = INDICTRANS_LANGUAGE_CODES[target_language]
        inputs = self.tokenizer(
            texts,
            padding="longest",
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(target_code),
                max_length=512,
                num_beams=5,
            )
        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)


def create_translator(backend: str) -> Any | None:
    if backend == "indictrans2":
        return IndicTrans2Translator()
    if backend == "nllb":
        return NLLBTranslator()
    if backend == "google":
        return None
    raise ValueError("TRANSLATION_BACKEND must be 'indictrans2', 'nllb', or 'google'.")


def translate_batch(
    texts: list[str], target_language: str, backend: str, translator: Any | None = None
) -> list[str]:
    if backend == "indictrans2":
        if not isinstance(translator, IndicTrans2Translator):
            raise RuntimeError("IndicTrans2 translator was not initialized.")
        return translator.translate_batch(texts, target_language)
    if backend == "nllb":
        if not isinstance(translator, NLLBTranslator):
            raise RuntimeError("NLLB translator was not initialized.")
        return translator.translate_batch(texts, target_language)
    if backend == "google":
        api_key = require_env("GOOGLE_TRANSLATE_API_KEY")
        return [translate_google(text, target_language, api_key) for text in texts]
    raise ValueError("TRANSLATION_BACKEND must be 'indictrans2', 'nllb', or 'google'.")


def call_openai(prompt: str) -> tuple[str, dict[str, Any]]:
    model = require_env("OPENAI_MODEL")
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {require_env('OPENAI_API_KEY')}", "Content-Type": "application/json"},
        json={"model": model, "input": prompt, "temperature": temperature(), "max_output_tokens": max_output_tokens()},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    parts = [item.get("text", "") for output in payload.get("output", []) for item in output.get("content", []) if item.get("type") == "output_text"]
    return "\n".join(parts), {"provider": "openai", "model": model, "api_response_id": payload.get("id")}


def call_gemini(prompt: str) -> tuple[str, dict[str, Any]]:
    model = require_env("GEMINI_MODEL")
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": require_env("GEMINI_API_KEY")},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperature(), "maxOutputTokens": max_output_tokens()}},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload["candidates"][0]["content"]["parts"]
    return "\n".join(part.get("text", "") for part in parts), {"provider": "gemini", "model": model}


def call_llama(prompt: str) -> tuple[str, dict[str, Any]]:
    base_url = require_env("LLAMA_BASE_URL").rstrip("/")
    model = require_env("LLAMA_MODEL")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {require_env('LLAMA_API_KEY')}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature(), "max_tokens": max_output_tokens()},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"], {"provider": "llama", "model": model, "api_response_id": payload.get("id")}


def call_openai_compatible(
    prompt: str,
    *,
    provider: str,
    api_key_env: str,
    model_env: str,
    base_url_env: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    base_url = require_env(base_url_env).rstrip("/")
    model = require_env(model_env)
    headers = {
        "Authorization": f"Bearer {require_env(api_key_env)}",
        "Content-Type": "application/json",
        **(extra_headers or {}),
    }
    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature(),
            "max_tokens": max_output_tokens(),
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"], {
        "provider": provider,
        "model": model,
        "api_response_id": payload.get("id"),
        "usage": payload.get("usage"),
    }


def call_groq(prompt: str) -> tuple[str, dict[str, Any]]:
    return call_openai_compatible(
        prompt,
        provider="groq",
        api_key_env="GROQ_API_KEY",
        model_env="GROQ_MODEL",
        base_url_env="GROQ_BASE_URL",
    )


def call_openrouter(prompt: str) -> tuple[str, dict[str, Any]]:
    return call_openai_compatible(
        prompt,
        provider="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        model_env="OPENROUTER_MODEL",
        base_url_env="OPENROUTER_BASE_URL",
        extra_headers={"X-Title": "Multilingual Safety Fairness Pilot"},
    )


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}. Add it to .env before running this command.")
    return value


def temperature() -> float:
    return float(os.getenv("TEMPERATURE", "0"))


def max_output_tokens() -> int:
    return int(os.getenv("MAX_OUTPUT_TOKENS", "800"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def sleep_briefly(provider: str | None = None) -> None:
    # Stay below public free-tier request limits during sequential collection.
    delays = {"openrouter": 3.2, "groq": 2.1, "gemini": 1.1}
    time.sleep(delays.get(provider, 0.15))
