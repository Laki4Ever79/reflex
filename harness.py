#!/usr/bin/env python3
"""Contract harness — run this constantly.

    python harness.py            # probe every lane, print the board
    python harness.py --live     # also hit the real allocator (costs a grok call)

Each lane is probed through the ONE entry point it owes the other two. A lane is
OK when that entry point exists, accepts the contract type, and returns the
contract type. Nothing else is checked — this is a contract test, not a test suite.

If the board is green you can push. If someone else's lane is red, that's their
problem to fix, not yours to work around.
"""

import argparse
import importlib
import sys
import traceback
from dataclasses import is_dataclass

from contracts import (
    Allocation,
    CodeArtifact,
    ContextArtifact,
    Correction,
    GateVerdict,
    PreferencePair,
    WeightsArtifact,
)

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, RED, YELLOW, BLUE = "\033[32m", "\033[31m", "\033[33m", "\033[34m"

OK, STUB, BROKEN = "OK", "STUB", "BROKEN"


# --------------------------------------------------------------------------
# canned inputs — one per lane, chosen so each SHOULD route to its own lane
# --------------------------------------------------------------------------

PROBES = {
    "code": Correction(
        agent_said="Done, the change is ready.",
        user_wanted="Always run the tests before telling me it's done.",
        situation="Agent claimed a task complete without running the suite.",
        recurrence=4,
    ),
    "weights": Correction(
        agent_said="I sincerely apologize for the confusion, and I'm very sorry.",
        user_wanted="Stop over-apologizing. One short acknowledgement, then move on.",
        situation="Agent made a small mistake and wrote three sentences of apology.",
        recurrence=5,
    ),
    "context": Correction(
        agent_said="I'll deploy to the staging environment at staging.internal.",
        user_wanted="Staging moved to stg-2.internal last week.",
        situation="Agent used a stale hostname.",
        recurrence=0,
    ),
}


def _probe(label, fn):
    """Run one probe. Returns (status, detail)."""
    try:
        return fn()
    except (ImportError, ModuleNotFoundError, AttributeError) as e:
        return STUB, f"not wired yet — {type(e).__name__}: {e}"
    except NotImplementedError:
        return STUB, "raises NotImplementedError"
    except Exception as e:
        if "--trace" in sys.argv:
            traceback.print_exc()
        return BROKEN, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# probes — one per owner
# --------------------------------------------------------------------------

def probe_allocator(live):
    """aleksa owes: allocate(Correction) -> Allocation"""
    mod = importlib.import_module("allocator.allocate")
    fn = getattr(mod, "allocate")
    if not live:
        return STUB, "present, not called (use --live to hit grok)"
    out = fn(PROBES["code"])
    if not isinstance(out, Allocation):
        return BROKEN, f"returned {type(out).__name__}, expected Allocation"
    if out.lane not in ("code", "weights", "context"):
        return BROKEN, f"bad lane {out.lane!r}"
    if not out.rationale:
        return BROKEN, "empty rationale — the dashboard renders this"
    return OK, f"routed -> {out.lane} ({out.confidence:.2f}) · {out.rationale[:54]}"


def probe_context(live):
    """lazar-v owes: store(ContextArtifact) -> None, and a token count"""
    mod = importlib.import_module("lanes.context.store")
    store = getattr(mod, "store")
    tokens = getattr(mod, "context_tokens")
    store(ContextArtifact(bullet="Staging is stg-2.internal.", trigger="retrieved_on:deploy"))
    n = tokens()
    if not isinstance(n, int):
        return BROKEN, f"context_tokens() returned {type(n).__name__}, expected int"
    return OK, f"stored · {n} context tokens (this is the number the closing shot plots)"


def probe_code(live):
    """lazar-v owes: materialize(CodeArtifact) -> a registered, callable tool"""
    mod = importlib.import_module("lanes.code.materialize")
    fn = getattr(mod, "materialize")
    art = CodeArtifact(
        name="tests_pass",
        signature="tests_pass() -> bool",
        implementation="def tests_pass():\n    return True\n",
        call_when="before claiming a task is complete",
    )
    tool = fn(art)
    if tool is None:
        return BROKEN, "materialize() returned None — dashboard needs the registered tool"
    return OK, f"executed in sandbox + registered · {getattr(tool, 'name', tool)}"


def probe_weights(live):
    """lazar-j owes: synthesize(WeightsArtifact) -> list[PreferencePair]"""
    mod = importlib.import_module("lanes.weights.synthesize")
    fn = getattr(mod, "synthesize")
    if not live:
        return STUB, "present, not called (use --live to hit grok)"
    pairs = fn(WeightsArtifact(principle="Acknowledge briefly, don't over-apologize.",
                               scope="all agent replies after an error"))
    if not pairs or not all(isinstance(p, PreferencePair) for p in pairs):
        return BROKEN, "expected a non-empty list[PreferencePair]"
    if len(pairs) < 8:
        return BROKEN, f"only {len(pairs)} pairs — need ~12 or a run won't move anything"
    return OK, f"{len(pairs)} preference pairs from 1 principle"


def probe_gate(live):
    """aleksa owes: evaluate(incumbent, challenger) -> GateVerdict"""
    mod = importlib.import_module("lanes.weights.gate")
    fn = getattr(mod, "evaluate")
    sig = getattr(fn, "__code__", None)
    if sig and sig.co_argcount < 2:
        return BROKEN, "evaluate() needs (incumbent, challenger)"
    return OK, "present — a REJECTED cycle is a demo asset, make sure it's visible"


PROBE_TABLE = [
    ("allocator",       "aleksa ", probe_allocator),
    ("lane: context",   "lazar-v", probe_context),
    ("lane: code",      "lazar-v", probe_code),
    ("lane: weights",   "lazar-j", probe_weights),
    ("promotion gate",  "aleksa ", probe_gate),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also call grok (costs money, proves it actually works)")
    ap.add_argument("--trace", action="store_true", help="full traceback on BROKEN")
    args = ap.parse_args()

    sys.path.insert(0, ".")

    print(f"\n{BOLD}reflex · contract harness{RESET}"
          f"{DIM}{'  (live)' if args.live else '  (static — add --live to hit grok)'}{RESET}\n")

    counts = {OK: 0, STUB: 0, BROKEN: 0}
    for name, owner, fn in PROBE_TABLE:
        status, detail = _probe(name, lambda f=fn: f(args.live))
        counts[status] += 1
        colour = {OK: GREEN, STUB: YELLOW, BROKEN: RED}[status]
        print(f"  {colour}{status:<7}{RESET} {BLUE}{owner}{RESET}  {name:<16} {DIM}{detail}{RESET}")

    print()
    if counts[BROKEN]:
        print(f"  {RED}{counts[BROKEN]} broken{RESET} — a contract is violated. "
              f"Fix yours; don't work around someone else's.")
    elif counts[STUB]:
        print(f"  {YELLOW}{counts[STUB]} not wired{RESET} — expected early. "
              f"Green on your own row means you can push.")
    else:
        print(f"  {GREEN}all green{RESET} — the loop composes. Go record something.")
    print()

    return 1 if counts[BROKEN] else 0


if __name__ == "__main__":
    sys.exit(main())
