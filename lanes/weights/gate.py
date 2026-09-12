"""Promote a new adapter only if it beats the incumbent. A rejection is a demo asset."""

from contracts import Adapter, GateVerdict

# Stand-in until real held-out eval exists. The decision logic is what matters today.
HELD_OUT_N = 8


def score(adapter: Adapter) -> float:
    """Stub scorer. Swap for held-out eval when adapters exist.

    trained_on is the stand-in metric: a challenger trained on fewer pairs
    loses. Stage a rejection by passing a weaker challenger.
    """
    return float(adapter.trained_on)


def evaluate(incumbent: Adapter | None, challenger: Adapter) -> GateVerdict:
    challenger_score = score(challenger)
    if incumbent is None:
        return GateVerdict(
            promoted=True,
            incumbent_score=0.0,
            challenger_score=challenger_score,
            held_out_n=HELD_OUT_N,
            note="PROMOTED — first adapter, no incumbent to beat.",
        )
    incumbent_score = score(incumbent)
    if challenger_score > incumbent_score:
        return GateVerdict(
            promoted=True,
            incumbent_score=incumbent_score,
            challenger_score=challenger_score,
            held_out_n=HELD_OUT_N,
            note=(
                f"PROMOTED — challenger {challenger_score:.1f} beat "
                f"incumbent {incumbent_score:.1f} on {HELD_OUT_N} held-out."
            ),
        )
    return GateVerdict(
        promoted=False,
        incumbent_score=incumbent_score,
        challenger_score=challenger_score,
        held_out_n=HELD_OUT_N,
        note=(
            f"REJECTED — challenger {challenger_score:.1f} did not beat "
            f"incumbent {incumbent_score:.1f}; incumbent kept."
        ),
    )
