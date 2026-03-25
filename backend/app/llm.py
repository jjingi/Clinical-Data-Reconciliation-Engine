"""OpenAI-backed reconciliation and data quality validation with caching."""

import asyncio
import hashlib
import json
import os
from typing import Any

import openai
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

# ── In-memory cache ──────────────────────────────────────────────────────

_cache: dict[str, Any] = {}


def _cache_key(prefix: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()}"


# ── OpenAI helper ────────────────────────────────────────────────────────


def _client() -> openai.AsyncOpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set in .env")
    return openai.AsyncOpenAI(api_key=key)


async def _chat_json(system: str, user: str, retries: int = 3) -> dict:
    """Call the model and return parsed JSON. Retries on rate limit with backoff."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for attempt in range(retries):
        try:
            resp = await _client().chat.completions.create(
                model=MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except openai.RateLimitError:
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
            else:
                raise HTTPException(status_code=429, detail="OpenAI rate limit — try again shortly")
        except openai.APIError as e:
            raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")
    return {}


# ── Prompts ──────────────────────────────────────────────────────────────

_RECONCILE_SYSTEM = """\
You are a clinical pharmacist AI assistant specialising in medication reconciliation across EHR systems.
Given conflicting medication records and patient context, determine the most clinically accurate regimen.

Consider these factors in order of importance:
1. Recency — more recently updated records are more likely current
2. Source reliability — high > medium > low
3. Clinical plausibility — given the patient's conditions and lab values
4. Consistency — agreement across multiple sources increases confidence

Respond with ONLY valid JSON matching this exact schema:
{
  "reconciled_medication": "medication name, dose, and frequency as a single string",
  "confidence_score": <float 0.0–1.0>,
  "reasoning": "detailed clinical reasoning referencing specific sources and patient context",
  "recommended_actions": ["action 1", "action 2"],
  "clinical_safety_check": "PASSED" or "FAILED"
}

Set clinical_safety_check to "FAILED" only when the reconciled medication poses a direct patient safety risk \
(e.g. contraindication with a known condition, dangerous dose given lab values).\
"""

_DATA_QUALITY_SYSTEM = """\
You are a clinical data quality analyst evaluating EHR patient records.

Score the record across four dimensions (integer 0–100 each):
- completeness: Are all critical clinical fields present and populated?
- accuracy: Are values clinically reasonable and self-consistent?
- timeliness: How current is the data? Records >6 months old score lower.
- clinical_plausibility: Are values physiologically possible (e.g. vital signs in human range)?

Calculate overall_score as a weighted average:
  (completeness × 0.25) + (accuracy × 0.30) + (timeliness × 0.20) + (clinical_plausibility × 0.25)
Round to the nearest integer.

Respond with ONLY valid JSON matching this exact schema:
{
  "overall_score": <integer 0–100>,
  "breakdown": {
    "completeness": <integer>,
    "accuracy": <integer>,
    "timeliness": <integer>,
    "clinical_plausibility": <integer>
  },
  "issues_detected": [
    {"field": "field.path", "issue": "human-readable description", "severity": "high"|"medium"|"low"}
  ]
}

Severity guide:
- high: patient safety risk (e.g. impossible vital sign, dangerous drug-disease mismatch)
- medium: data integrity concern (e.g. missing allergy list, stale record)
- low: minor quality issue (e.g. incomplete demographics)\
"""


def _format_sources(sources: list[dict]) -> str:
    lines = []
    for i, s in enumerate(sources, 1):
        date = s.get("last_updated") or s.get("last_filled") or "unknown date"
        reliability = s.get("source_reliability", "unknown")
        lines.append(f"{i}. {s['system']} (reliability: {reliability}, date: {date}): {s['medication']}")
    return "\n".join(lines)


def _format_labs(labs: dict) -> str:
    if not labs:
        return "none"
    return ", ".join(f"{k}: {v}" for k, v in labs.items())


# ── Public functions ─────────────────────────────────────────────────────


async def reconcile_medication(payload: dict) -> dict:
    key = _cache_key("reconcile", payload)
    if key in _cache:
        return _cache[key]

    ctx = payload.get("patient_context", {})
    sources = payload.get("sources", [])

    user_message = f"""\
Patient context:
- Age: {ctx.get("age") or "not provided"}
- Conditions: {", ".join(ctx.get("conditions", [])) or "none listed"}
- Recent labs: {_format_labs(ctx.get("recent_labs", {}))}

Conflicting medication records ({len(sources)} source{"s" if len(sources) != 1 else ""}):
{_format_sources(sources)}

Reconcile the medication and provide clinical reasoning.\
"""

    result = await _chat_json(_RECONCILE_SYSTEM, user_message)
    _cache[key] = result
    return result


async def validate_data_quality(payload: dict) -> dict:
    key = _cache_key("dq", payload)
    if key in _cache:
        return _cache[key]

    user_message = f"""\
Evaluate the data quality of the following patient record:

{json.dumps(payload, indent=2, default=str)}\
"""

    result = await _chat_json(_DATA_QUALITY_SYSTEM, user_message)
    _cache[key] = result
    return result
