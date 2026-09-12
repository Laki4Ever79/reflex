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
    _write(state)


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
