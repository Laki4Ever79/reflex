"""Pipe a correction in, print lane + rationale + artifact. Iterate prompt.txt here."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from contracts import Correction

from .allocate import allocate


def main() -> None:
    p = argparse.ArgumentParser(description="Allocate one correction to a lane.")
    p.add_argument("--said", required=True, help="what the agent produced")
    p.add_argument("--wanted", required=True, help="the correction")
    p.add_argument("--situation", default="", help="what was happening")
    p.add_argument("--recurrence", type=int, default=0)
    args = p.parse_args()

    out = allocate(
        Correction(
            agent_said=args.said,
            user_wanted=args.wanted,
            situation=args.situation,
            recurrence=args.recurrence,
        )
    )

    print(f"lane:        {out.lane}")
    print(f"confidence:  {out.confidence:.2f}")
    print(f"rationale:   {out.rationale}")
    print()
    print("artifact:")
    for key, value in asdict(out.artifact).items():
        lines = str(value).splitlines() or [""]
        print(f"  {key}:")
        for line in lines:
            print(f"    {line}")


if __name__ == "__main__":
    main()
