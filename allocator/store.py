"""Persist allocations to state.json for the dashboard. No imports across lanes."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from contracts import Allocation, Correction

from .allocate import allocate
from .cluster import assign_cluster

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"

EMPTY_STATE = {
    "corrections": [],
    "clusters": {},
    "context_tokens": 0,
    "queue_depth": 0,
    "adapter_version": None,
}


def load() -> dict:
    if not STATE_PATH.exists():
        return json.loads(json.dumps(EMPTY_STATE))
    return json.loads(STATE_PATH.read_text())


def _write(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(STATE_PATH)


def _artifact_fields(artifact) -> dict:
    if is_dataclass(artifact) and not isinstance(artifact, type):
        return asdict(artifact)
    raise TypeError(f"artifact is not a dataclass: {type(artifact).__name__}")


def append(correction: Correction, allocation: Allocation) -> None:
    state = load()
    cluster = getattr(correction, "cluster", None)
    if not cluster:
        known = list(state["clusters"])
        cluster = assign_cluster(correction, known)
        correction.cluster = cluster
    next_id = 1 + max((row["id"] for row in state["corrections"]), default=0)
    state["corrections"].append(
        {
            "id": next_id,
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "agent_said": correction.agent_said,
            "user_wanted": correction.user_wanted,
            "situation": correction.situation,
            "cluster": cluster,
            "recurrence": correction.recurrence,
            "lane": allocation.lane,
            "rationale": allocation.rationale,
            "confidence": allocation.confidence,
            "artifact": _artifact_fields(allocation.artifact),
        }
    )
    state["clusters"] = dict(
        Counter(row["cluster"] for row in state["corrections"])
    )
    _recount_tokens(state)
    _write(state)


def _recount_tokens(state: dict) -> None:
    """The number the closing chart plots, and the counterfactual beside it.

    context_tokens is what the agent actually carries on every call: only the
    bullets that landed in the context lane. if_all_context is what a one-lane
    agent would carry - every correction written down as a note - which is the
    line that climbs while ours stays flat.

    Derived from state rather than read from the context lane's in-memory list,
    so it survives a restart and reflects the seeded history.
    """
    try:
        from lanes.context.store import _count_tokens
    except Exception:  # noqa: BLE001
        def _count_tokens(t: str) -> int:
            return max(1, len(t) // 4)

    rows = state.get("corrections", [])
    carried = 0
    counterfactual = 0
    for r in rows:
        art = r.get("artifact") or {}
        bullet = art.get("bullet") or ""
        if r.get("lane") == "context" and bullet:
            carried += _count_tokens(bullet)
        # what this learning would have cost if it had been written down
        counterfactual += _count_tokens(bullet or r.get("user_wanted", ""))

    state["context_tokens"] = carried
    state["if_all_context"] = counterfactual


def allocate_and_store(c: Correction) -> Allocation:
    state = load()
    known = list(dict.fromkeys(
        list(state.get("clusters", {}))
        + [row["cluster"] for row in state["corrections"]]
    ))
    cluster = assign_cluster(c, known)
    c.cluster = cluster
    c.recurrence = sum(1 for row in state["corrections"] if row["cluster"] == cluster)
    allocation = allocate(c)
    append(c, allocation)
    return allocation
