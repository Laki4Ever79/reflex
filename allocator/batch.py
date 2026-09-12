"""Score the allocator against a labelled CSV. Agreement rate is the metric."""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from contracts import Correction

from .allocate import AllocationError, allocate

LANES = ("code", "weights", "context")


def _row_to_correction(row: dict) -> Correction:
    return Correction(
        agent_said=row["agent_said"],
        user_wanted=row["user_wanted"],
        situation=row.get("situation", ""),
        recurrence=int(row.get("recurrence") or 0),
    )


def _run_row(i: int, row: dict) -> dict:
    expected = row["expected"].strip().lower()
    try:
        out = allocate(_row_to_correction(row))
        actual = out.lane
        conf = out.confidence
        rationale = out.rationale
        err = ""
    except AllocationError as e:
        actual = "error"
        conf = None
        rationale = str(e)
        err = str(e)
    agree = actual == expected
    return {
        "i": i,
        "expected": expected,
        "actual": actual,
        "agree": agree,
        "confidence": conf,
        "rationale": rationale,
        "error": err,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Batch-allocate labelled corrections.")
    p.add_argument("csv_path", help="CSV with agent_said,user_wanted,situation,recurrence,expected")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    path = Path(args.csv_path)
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("empty csv", file=sys.stderr)
        sys.exit(1)

    results: list[dict | None] = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(_run_row, i, row): i for i, row in enumerate(rows)}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()

    print(f"{'#':<3} {'expected':<10} {'actual':<10} {'verdict':<10} {'conf':<6} rationale")
    n_agree = 0
    confusion = {e: {a: 0 for a in (*LANES, "error")} for e in LANES}
    for r in results:
        assert r is not None
        if r["agree"]:
            n_agree += 1
        verdict = "agree" if r["agree"] else "disagree"
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "—"
        rationale = r["rationale"].replace("\n", " ")
        print(
            f"{r['i']+1:<3} {r['expected']:<10} {r['actual']:<10} "
            f"{verdict:<10} {conf:<6} {rationale}"
        )
        if r["expected"] in confusion:
            actual_key = r["actual"] if r["actual"] in confusion[r["expected"]] else "error"
            confusion[r["expected"]][actual_key] += 1

    n = len(results)
    print()
    print(f"agreement: {n_agree}/{n} ({100.0 * n_agree / n:.0f}%)")
    print()
    print("confusion (rows=expected, cols=predicted):")
    print(f"          {'code':>8} {'weights':>8} {'context':>8} {'error':>8}")
    for expected in LANES:
        cells = " ".join(f"{confusion[expected][a]:>8}" for a in (*LANES, "error"))
        print(f"{expected:<10}{cells}")


if __name__ == "__main__":
    main()
