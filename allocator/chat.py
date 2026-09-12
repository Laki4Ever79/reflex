"""The agent the user actually talks to, and the detector that notices a correction.

The point of the demo is that a correction is not a form. It is something you
say to the agent in the ordinary way -- "no, not like that" -- and the system
notices, routes it, and behaves differently afterwards.

Two grok calls per turn:
  detect()  is this message a correction of what the agent just said?
  reply()   the agent's answer, with whatever it has already learned applied
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

MODEL = "grok-4.6"
BASE_URL = "https://api.x.ai/v1"

AGENT_SYSTEM = """You are a coding assistant working in a Python repo.
Be brief: two or three sentences, no bullet lists unless asked.
You cannot actually run commands - describe what you would do, concisely."""

DETECT_SYSTEM = """Decide whether the user's latest message is a CORRECTION of
what the assistant just said, or an ordinary request/question.

A CORRECTION tells the assistant it did something wrong, or how it should
behave instead. "Don't do X", "always do Y first", "stop doing Z", "that's
wrong, I wanted W", "again - shorter" are corrections.
A new task, a question, or an approval is NOT a correction.

Return JSON only:
{"is_correction": true|false,
 "agent_said": "<what the assistant did that was wrong, one line, or empty>",
 "user_wanted": "<the rule the user is asking for, one line, or empty>",
 "situation": "<what was happening, one line, or empty>"}

If is_correction is false, the other fields are empty strings."""


def _client() -> OpenAI:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not set")
    return OpenAI(api_key=key, base_url=BASE_URL)


def _learned_context(state: dict) -> str:
    """Context-lane bullets, injected into the agent's system prompt.

    This is what makes the context lane visible in the product: a correction
    routed to context changes how the agent answers on the very next turn.
    """
    bullets = [
        c["artifact"].get("bullet", "")
        for c in state.get("corrections", [])
        if c.get("lane") == "context" and isinstance(c.get("artifact"), dict)
    ]
    bullets = [b for b in bullets if b]
    if not bullets:
        return ""
    lines = "\n".join(f"- {b}" for b in bullets)
    return f"\n\nThings this user has told you before:\n{lines}"


def detect(messages: list[dict]) -> dict:
    """Was the last user message a correction? Returns the detector's verdict."""
    if len(messages) < 2:
        return {"is_correction": False, "agent_said": "", "user_wanted": "", "situation": ""}

    tail = messages[-4:]
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in tail)
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": DETECT_SYSTEM},
                  {"role": "user", "content": convo}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        d = json.loads(r.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"is_correction": False, "agent_said": "", "user_wanted": "", "situation": ""}
    return {
        "is_correction": bool(d.get("is_correction")),
        "agent_said": str(d.get("agent_said") or "")[:400],
        "user_wanted": str(d.get("user_wanted") or "")[:400],
        "situation": str(d.get("situation") or "")[:400],
    }


def reply_stream(messages: list[dict], state: dict):
    """The agent's answer, token by token.

    Grok takes ~7s for a short reply. Streaming does not make it faster, it
    makes the wait legible - the first words land in about a second and the
    demo stops looking stalled.
    """
    system = AGENT_SYSTEM + _learned_context(state)
    stream = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}] + messages[-12:],
        temperature=0.3,
        max_tokens=400,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


def reply(messages: list[dict], state: dict) -> str:
    """The agent's answer, with context-lane learnings applied."""
    system = AGENT_SYSTEM + _learned_context(state)
    r = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}] + messages[-12:],
        temperature=0.3,
        max_tokens=400,
    )
    return (r.choices[0].message.content or "").strip()
