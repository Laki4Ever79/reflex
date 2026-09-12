"""Pinned interfaces between the three lanes.

Three people build three lanes in parallel and only these shapes cross the
boundary. Agree them once, then nobody blocks on anybody.

Do not change anything in this file without telling the other two.
"""

from dataclasses import dataclass, field
from typing import Literal, Union

Lane = Literal["code", "weights", "context"]

# Recurrence required before a correction is eligible for the weights lane.
# High write cost is only justified by high read frequency. Lowered for demo.
WEIGHTS_RECURRENCE_THRESHOLD = 3

# Queued pairs required before a training run is triggered. Depth, not a clock:
# don't burn a GPU because it's 3am and two corrections came in.
TRAINING_QUEUE_DEPTH = 50


# --------------------------------------------------------------------------
# allocator input
# --------------------------------------------------------------------------

@dataclass
class Correction:
    agent_said: str      # what the agent produced
    user_wanted: str     # the correction
    situation: str       # what was happening when it went wrong
    recurrence: int = 0  # prior corrections in this cluster


# --------------------------------------------------------------------------
# lane artifacts
# --------------------------------------------------------------------------

@dataclass
class CodeArtifact:
    """A deterministic function. The only lane that promises rather than biases."""
    name: str
    signature: str
    implementation: str  # python source, executed in a Daytona sandbox
    call_when: str       # when the agent should invoke it


@dataclass
class WeightsArtifact:
    """A principle, NOT training pairs.

    Allocation and synthesis stay separate: the allocator decides, then L2
    expands one principle into ~12 pairs across varied contexts. That's how 20
    corrections become 200+ examples, which is what makes a training run move.
    """
    principle: str
    scope: str  # where it applies


@dataclass
class ContextArtifact:
    """A structured bullet. Lane of last resort — this one is taxed on every read."""
    bullet: str
    trigger: str  # "always" | "retrieved_on:<cue>"


Artifact = Union[CodeArtifact, WeightsArtifact, ContextArtifact]


# --------------------------------------------------------------------------
# allocator output
# --------------------------------------------------------------------------

@dataclass
class Allocation:
    lane: Lane
    rationale: str      # one sentence naming the property that decided it
    confidence: float   # 0.0 - 1.0
    artifact: Artifact


# --------------------------------------------------------------------------
# weights lane: training + the promotion gate
# --------------------------------------------------------------------------

@dataclass
class PreferencePair:
    """A correction is natively a preference pair. Use DPO/ORPO, not SFT."""
    prompt: str
    chosen: str    # what the user wanted
    rejected: str  # what the agent said


@dataclass
class Adapter:
    version: int
    path: str
    trained_on: int = 0          # pair count
    parent: int | None = None    # version this was trained from


@dataclass
class GateVerdict:
    """A new adapter must beat its predecessor on held-out corrections or it is
    discarded. We mutate an assistant while nobody is watching; if a cycle makes
    it worse it has to be caught here."""
    promoted: bool
    incumbent_score: float
    challenger_score: float
    held_out_n: int
    note: str = ""


# --------------------------------------------------------------------------
# what the dashboard renders
# --------------------------------------------------------------------------

@dataclass
class LaneState:
    items: list = field(default_factory=list)
    context_tokens: int = 0  # the number that must not grow


@dataclass
class ReflexState:
    code: LaneState = field(default_factory=LaneState)
    weights: LaneState = field(default_factory=LaneState)
    context: LaneState = field(default_factory=LaneState)
    adapter: Adapter | None = None
    queue_depth: int = 0
