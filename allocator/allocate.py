"""One call path: Correction -> grok-4.6 -> Allocation.

Malformed output is retried once, then AllocationError. No default lane.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from contracts import (
    Allocation,
    CodeArtifact,
    ContextArtifact,
    Correction,
    WeightsArtifact,
)

PROMPT_PATH = Path(__file__).resolve().parent / "prompt.txt"
XAI_BASE_URL = "https://api.x.ai/v1"
MODEL = "grok-4.6"


class AllocationError(Exception):
    """Raised when the model output cannot be parsed after one retry."""


def _client() -> OpenAI:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise AllocationError("XAI_API_KEY is not set")
    return OpenAI(api_key=key, base_url=XAI_BASE_URL)


def _user_message(c: Correction) -> str:
    return (
        f"agent_said: {c.agent_said}\n"
        f"user_wanted: {c.user_wanted}\n"
        f"situation: {c.situation}\n"
        f"recurrence: {c.recurrence}\n"
    )


def _extract_object(text: str) -> dict:
    text = text.strip()
    candidates = [text]
    if text.startswith("```"):
        body = text.split("\n", 1)[-1]
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
        candidates.append(body.strip())
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("response is not a JSON object")


def _require_str(d: dict, key: str) -> str:
    value = d.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or empty field {key!r}")
    return value


def _parse_allocation(raw: str) -> Allocation:
    data = _extract_object(raw)
    lane = data.get("lane")
    if lane not in ("code", "weights", "context"):
        raise ValueError(f"bad lane {lane!r}")
    rationale = _require_str(data, "rationale")
    conf = data.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ValueError("bad confidence")
    confidence = float(conf)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence out of range")
    art = data.get("artifact")
    if not isinstance(art, dict):
        raise ValueError("missing artifact object")
    if lane == "code":
        artifact = CodeArtifact(
            name=_require_str(art, "name"),
            signature=_require_str(art, "signature"),
            implementation=_require_str(art, "implementation"),
            call_when=_require_str(art, "call_when"),
        )
    elif lane == "weights":
        artifact = WeightsArtifact(
            principle=_require_str(art, "principle"),
            scope=_require_str(art, "scope"),
        )
    else:
        artifact = ContextArtifact(
            bullet=_require_str(art, "bullet"),
            trigger=_require_str(art, "trigger"),
        )
    return Allocation(
        lane=lane,
        rationale=rationale,
        confidence=confidence,
        artifact=artifact,
    )


def _complete(client: OpenAI, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("empty model response")
    return content


def allocate(c: Correction) -> Allocation:
    system = PROMPT_PATH.read_text()
    user = _user_message(c)
    client = _client()
    last_err: Exception | None = None
    for _ in range(2):
        try:
            return _parse_allocation(_complete(client, system, user))
        except AllocationError:
            raise
        except Exception as e:
            last_err = e
    raise AllocationError(f"unparseable after retry: {last_err}") from last_err
