"""L2 synthesis: expand one principle into varied preference pairs via grok-4.6.

This is what turns 20 corrections into 200+ training examples — without it a
training run on a handful of pairs won't move anything.
"""

import json
import os
import re

import requests
from dotenv import load_dotenv

from contracts import PreferencePair, WeightsArtifact

load_dotenv()

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = "grok-4.6"
PAIRS_PER_PRINCIPLE = 12

SYSTEM_PROMPT = f"""You expand ONE behavioural principle into {PAIRS_PER_PRINCIPLE} preference \
pairs for DPO training. Each pair is a different, realistic situation where the principle \
applies — vary topic, phrasing, and context; do not repeat the same scenario reworded.

Given:
  principle: <the behaviour to instill>
  scope: <where it applies>

Return JSON only, no prose:
{{
  "pairs": [
    {{"prompt": "...", "chosen": "...", "rejected": "..."}}
    ... exactly {PAIRS_PER_PRINCIPLE} entries
  ]
}}

"chosen" demonstrates the principle. "rejected" is a realistic agent response that violates \
it — not a strawman, the kind of response that actually gets corrected."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in response: {text[:200]!r}")
    return json.loads(match.group(0))


def _call_grok(artifact: WeightsArtifact, api_key: str) -> dict:
    resp = requests.post(
        XAI_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": XAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"principle: {artifact.principle}\nscope: {artifact.scope}",
                },
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


def synthesize(artifact: WeightsArtifact) -> list[PreferencePair]:
    """~12 PreferencePairs applying `artifact.principle` across varied situations.

    Malformed model output: retry once, then raise. No fallback — a silently
    truncated pair list would quietly starve every training run downstream.
    """
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("XAI_API_KEY not set — put it in reflex/.env")

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            data = _call_grok(artifact, api_key)
            pairs = [
                PreferencePair(prompt=p["prompt"], chosen=p["chosen"], rejected=p["rejected"])
                for p in data["pairs"]
            ]
            if len(pairs) < 8:
                raise ValueError(f"only {len(pairs)} pairs, need ~{PAIRS_PER_PRINCIPLE}")
            return pairs
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            last_error = e
    raise RuntimeError(f"synthesize: malformed response after retry — {last_error}") from last_error
