"""One explicit, budgeted sample request. Never output credentials or error bodies."""
import argparse
import asyncio
from dataclasses import asdict, replace
import json
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiohttp
from nuri.config import Settings
from nuri.limits import DailyBudget
from nuri.provider import parse_result, request_body

SAMPLE = "I read a short article every morning."


async def probe(model, variant):
    settings = replace(Settings.from_env(), model=model)
    report = {"model": model, "variant": variant, "status": None}
    if not settings.api_enabled or not settings.gemini_key:
        report["outcome"] = "credentials_not_ready"
        return report
    payload = request_body(SAMPLE, "learn") if variant == "structured" else {
        "contents": [{"role": "user", "parts": [{"text": "Translate into Korean: " + SAMPLE}]}],
        "generationConfig": {"maxOutputTokens": 2048, "thinkingConfig": {"thinkingLevel": "low"}},
    }
    DailyBudget(settings.state_dir / "usage.sqlite", settings.daily_request_limit).reserve()
    started = time.monotonic()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40), trust_env=False) as session:
            async with session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_key}, json=payload, allow_redirects=False,
            ) as response:
                report["status"] = response.status
                report["content_type"] = response.headers.get("Content-Type", "")[:100]
                report["server"] = response.headers.get("Server", "")[:80]
                data = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    data.extend(chunk)
                    if len(data) > 131072:
                        report["outcome"] = "response_too_large"
                        return report
                try:
                    body = json.loads(data)
                except (ValueError, UnicodeError):
                    report["outcome"] = "non_json_response"
                    return report
                if response.status != 200:
                    error = body.get("error", {}) if isinstance(body, dict) else {}
                    status = error.get("status")
                    if status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED", "NOT_FOUND", "INTERNAL"}:
                        report["provider_status"] = status
                    message = str(error.get("message", "")).lower()
                    report["error_categories"] = [category for category, terms in {
                        "overload_or_capacity": ("overload", "capacity", "high demand"),
                        "temporary_unavailability": ("unavailable", "temporar", "try again"),
                        "quota_or_rate_limit": ("quota", "rate limit", "resource exhausted"),
                        "model_not_found": ("model not found", "not found for api version"),
                        "unsupported_parameter": ("unknown name", "unsupported", "unrecognized field"),
                    }.items() if any(term in message for term in terms)]
                    report["outcome"] = "provider_error"
                elif variant == "structured":
                    result = parse_result(body, SAMPLE, "learn")
                    report["outcome"] = "validated_translation"
                    report["sample_result"] = asdict(result)
                else:
                    report["outcome"] = "generation_accepted"
                    report["finish_reasons"] = [c.get("finishReason") for c in body.get("candidates", [])]
    except asyncio.TimeoutError:
        report["outcome"] = "timeout"
    except aiohttp.ClientError:
        report["outcome"] = "network_error"
    except Exception:
        report["outcome"] = "unvalidated_response"
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return report


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["gemini-3.8-flash", "gemini-3.5-flash-lite"], required=True)
    parser.add_argument("--variant", choices=["structured", "minimal"], default="structured")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(probe(args.model, args.variant)), ensure_ascii=False))
    except Exception:
        print(json.dumps({"outcome": "diagnostic_setup_failed"}))
