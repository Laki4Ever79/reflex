"""Weights lane: principle -> pairs -> queue -> (eventually) adapter.

Single entry point for whoever hands this lane a WeightsArtifact (allocator /
integration): synthesize, enqueue, and fire training only if the queue is deep
enough. Every piece is also reachable directly — see queue.py, synthesize.py,
train.py.
"""

from contracts import Adapter, WeightsArtifact
from lanes.weights import queue
from lanes.weights.synthesize import synthesize
from lanes.weights.train import maybe_train


def on_weights_artifact(artifact: WeightsArtifact) -> Adapter | None:
    """principle -> ~12 pairs -> queue -> train only if queue.ready()."""
    pairs = synthesize(artifact)
    queue.enqueue(pairs)
    return maybe_train()
