"""Replay correction history into state.json so the demo starts warm.

    python -m allocator.seed --reset demo_seed.csv

The recurrence counter crossing its threshold ON CAMERA is the demo's best
frame: the same correction routes to CONTEXT at recurrence 2 and to WEIGHTS at
3. From a cold start that frame is unreachable, because nothing has recurred.

This replays real prior corrections through the normal path — assign_cluster,
recurrence from cluster membership, allocate, append. Nothing is faked: the
lanes are decided by the live allocator exactly as they are during the demo.

Afterwards it prints which clusters are one correction away from the threshold.
Those are the ones to type on camera.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from contracts import WEIGHTS_RECURRENCE_THRESHOLD, Correction

from .allocate import AllocationError
from .store import STATE_PATH, allocate_and_store, load


def _rows(path: Path) -> list[Correction]:
    with path.open(newline="") as f:
        return [
            Correction(
                agent_said=r["agent_said"],
                user_wanted=r["user_wanted"],
                situation=r.get("situation", ""),
                recurrence=0,  # recomputed from cluster membership
            )
            for r in csv.DictReader(f)
        ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path")
    ap.add_argument("--reset", action="store_true", help="wipe state.json first")
    args = ap.parse_args()

    if args.reset and STATE_PATH.exists():
        STATE_PATH.unlink()
        print(f"reset {STATE_PATH.name}")

    corrections = _rows(Path(args.csv_path))
    print(f"seeding {len(corrections)} corrections in order\n")

    for i, c in enumerate(corrections, 1):
        try:
            a = allocate_and_store(c)
            print(
                f"  {i:>2}. {c.cluster:<28} recurrence={c.recurrence} "
                f"-> {a.lane.upper()}"
            )
        except AllocationError as e:
            print(f"  {i:>2}. FAILED — {e}")

    state = load()
    counts = state["clusters"]
    thr = WEIGHTS_RECURRENCE_THRESHOLD

    print(f"\nstate.json: {len(state['corrections'])} corrections, "
          f"{len(counts)} clusters, threshold={thr}\n")

    primed = sorted(k for k, v in counts.items() if v == thr - 1)
    if primed:
        print("ONE MORE CROSSES THE THRESHOLD — type one of these on camera:")
        for k in primed:
            print(f"  {k:<28} at {counts[k]}, next one routes to WEIGHTS")
    else:
        print("NOTHING IS PRIMED. No cluster sits at threshold-1, so the "
              "counter cannot cross on camera.")
        print("Add another correction in the same cluster as one of these:")
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:5]:
            print(f"  {k:<28} at {v}")


if __name__ == "__main__":
    main()
