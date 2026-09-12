"""Preference-pair queue for the weights lane. Depth triggers training, not a clock."""

import json
from dataclasses import asdict
from pathlib import Path

from contracts import TRAINING_QUEUE_DEPTH, PreferencePair

QUEUE_PATH = Path(__file__).parent / "queue.jsonl"


def enqueue(pairs: list[PreferencePair]) -> int:
    """Appends pairs to the queue, returns the new depth."""
    with QUEUE_PATH.open("a") as f:
        for p in pairs:
            f.write(json.dumps(asdict(p)) + "\n")
    return queue_depth()


def queue_depth() -> int:
    if not QUEUE_PATH.exists():
        return 0
    with QUEUE_PATH.open() as f:
        return sum(1 for _ in f)


def drain() -> list[PreferencePair]:
    """Pops everything currently queued. Called at the start of a training run."""
    if not QUEUE_PATH.exists():
        return []
    with QUEUE_PATH.open() as f:
        pairs = [PreferencePair(**json.loads(line)) for line in f]
    QUEUE_PATH.unlink()
    return pairs


def ready() -> bool:
    return queue_depth() >= TRAINING_QUEUE_DEPTH
