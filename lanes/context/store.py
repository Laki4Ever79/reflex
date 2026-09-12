"""Context lane — lane of last resort. Taxed on every read.

Owes the other two lanes exactly two things:
    store(ContextArtifact) -> None
    context_tokens() -> int

The token count is the number the closing shot of the video plots, so it has
to be honest: it must only grow when a bullet is actually stored, never be
guessed or faked.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from contracts import ContextArtifact
import re



DEBUG = True  # flip to False once this stops needing eyes on it

# In-memory store. Reset between process runs — that's fine, the demo runs once.
_BULLETS: list[ContextArtifact] = []

_RETRIEVED_ON_RE = re.compile(r"^retrieved_on:.+$")


def _log(msg: str) -> None:
    if DEBUG:
        print(f"[context.store] {msg}")


def _validate_trigger(trigger: str) -> None:
    """Trigger must be 'always' or 'retrieved_on:<cue>'. Anything else is a
    contract violation from whoever built the artifact — fail loudly here,
    don't let a malformed bullet silently sit in context forever."""
    if trigger == "always" or _RETRIEVED_ON_RE.match(trigger):
        return
    raise ValueError(
        f"bad trigger {trigger!r} — expected 'always' or 'retrieved_on:<cue>'"
    )


def _count_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars/token is the standard back-of-envelope
    ratio for English text. Good enough for a counter that has to move
    visibly and consistently upward — it does NOT need to match a real
    tokenizer exactly, it needs to never lie about direction."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def store(artifact: ContextArtifact) -> None:
    _log(f"store() called with bullet={artifact.bullet!r} trigger={artifact.trigger!r}")

    _validate_trigger(artifact.trigger)

    _BULLETS.append(artifact)
    tokens_added = _count_tokens(artifact.bullet)

    _log(f"accepted — +{tokens_added} tokens, {len(_BULLETS)} bullets stored total")


def context_tokens() -> int:
    total = sum(_count_tokens(b.bullet) for b in _BULLETS)
    _log(f"context_tokens() -> {total} (across {len(_BULLETS)} bullets)")
    return total


def active_bullets(cue: str | None = None) -> list[ContextArtifact]:
    """What should actually get loaded into a turn's prompt: every 'always'
    bullet, plus any 'retrieved_on:<cue>' bullet whose cue matches. Not part
    of the pinned contract (harness doesn't call it) but every other lane
    that wants to *use* context instead of just count it will need this."""
    active = [
        b for b in _BULLETS
        if b.trigger == "always" or b.trigger == f"retrieved_on:{cue}"
    ]
    _log(f"active_bullets(cue={cue!r}) -> {len(active)} of {len(_BULLETS)}")
    return active


def reset() -> None:
    """Testing/demo helper only — NOT part of the pinned contract."""
    _log("reset() — clearing all stored bullets")
    _BULLETS.clear()


if __name__ == "__main__":
    # Standalone sanity check — run this BEFORE touching harness.py.
    print("=== standalone test, no harness ===")
    store(ContextArtifact(bullet="Staging is stg-2.internal.", trigger="retrieved_on:deploy"))
    store(ContextArtifact(bullet="Always answer in the user's language.", trigger="always"))
    print("tokens after 2 stores:", context_tokens())
    print("active for cue=deploy:", [b.bullet for b in active_bullets("deploy")])
    print("active for cue=None:  ", [b.bullet for b in active_bullets(None)])

    try:
        store(ContextArtifact(bullet="bad one", trigger="sometimes"))
        print("FAIL: bad trigger should have raised")
    except ValueError as e:
        print("OK: bad trigger correctly rejected ->", e)