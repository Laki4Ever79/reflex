"""Assign a correction to a cluster so recurrence is counted, not typed."""

from __future__ import annotations

import json
import re

from contracts import Correction

from .allocate import MODEL, _client

CLUSTER_PROMPT = """You label one user-correction so similar mistakes share a cluster.

Return JSON only: {"cluster": "kebab-case-label"}

Rules:
- If this is the SAME CLASS of mistake as a known label, reuse that label EXACTLY.
- If it is a new class, invent a short kebab-case label (2-4 words).
- Do not merge unrelated classes. A stale hostname is not over-apologising.
  A test-before-done rule is not a tone complaint.
- Labels are lowercase kebab-case: letters, numbers, hyphens only.
"""


def _kebab(label: str) -> str:
    s = label.strip().lower().replace("_", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        raise ValueError("empty cluster label")
    return s


def _parse_label(raw: str) -> str:
    data = json.loads(raw)
    if not isinstance(data, dict) or "cluster" not in data:
        raise ValueError("response missing cluster")
    return _kebab(str(data["cluster"]))


def assign_cluster(c: Correction, known: list[str]) -> str:
    known_line = ", ".join(known) if known else "(none yet)"
    user = (
        f"known clusters: {known_line}\n"
        f"agent_said: {c.agent_said}\n"
        f"user_wanted: {c.user_wanted}\n"
        f"situation: {c.situation}\n"
    )
    client = _client()
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": CLUSTER_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            label = _parse_label(content)
            if known and label not in known:
                # Model may restyle an existing label. Reuse if kebab-equal.
                for k in known:
                    if _kebab(k) == label:
                        return k
            return label
        except Exception as e:
            last_err = e
            if attempt == 0:
                user = (
                    user
                    + f"\nYour previous response could not be parsed: {e}. "
                    "Return only {\"cluster\": \"kebab-case-label\"}."
                )
    raise ValueError(f"cluster label unparseable after retry: {last_err}") from last_err
