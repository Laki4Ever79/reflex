"""The first thing to run, per PLAN.md: prove the sandbox -> install -> train ->
adapter-back loop works end to end, on junk data, before building anything else on
top of it.

Run from the reflex/ root:
    python -m lanes.weights.smoke_test
"""

from contracts import PreferencePair
from lanes.weights.train import train

JUNK_PAIRS = [
    PreferencePair(
        prompt="The user asks for a one-line status update.",
        chosen="Done.",
        rejected="I sincerely apologize for any inconvenience — here is a lengthy update.",
    ),
    PreferencePair(
        prompt="The user asks what 2+2 is.",
        chosen="4",
        rejected="That's a great question! Let me think through this step by step...",
    ),
    PreferencePair(
        prompt="The user says the deploy failed.",
        chosen="Rolling back now.",
        rejected="I'm so sorry to hear that, this must be frustrating for you.",
    ),
]


def main():
    print("smoke test: sandbox up, deps install, 20-step DPO run on junk data...")
    adapter = train(JUNK_PAIRS, max_steps=20)
    print(f"\nOK — adapter v{adapter.version} at {adapter.path} "
          f"(trained_on={adapter.trained_on}, parent={adapter.parent})")


if __name__ == "__main__":
    main()
