"""Mirror every routing decision into Convex, fire-and-forget.

state.json is the working copy and it does not survive a Render deploy - the
filesystem is ephemeral, so every push resets the demo to its seed. Convex is
the only store here that outlives that, so it holds the durable record: what was
corrected, where it went, why, and what the context tax was at the time.

Deliberately best-effort. A write happens on a background thread and every
failure is swallowed: if Convex is unreachable or unconfigured, the product is
completely unaffected and simply loses the archive for those rows. Nothing in
the request path waits on it.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

TIMEOUT = 5


def _url() -> str | None:
    base = (os.environ.get("CONVEX_URL") or "").strip().rstrip("/")
    return f"{base}/api/mutation" if base else None


def _post(payload: dict) -> None:
    url = _url()
    if not url:
        return
    body = json.dumps({
        "path": "corrections:record",
        "args": payload,
        "format": "json",
    }).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status >= 300:
                log.debug("convex mirror: HTTP %s", r.status)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.debug("convex mirror skipped: %s", e)


def _query(path: str, args: dict | None = None):
    base = (os.environ.get("CONVEX_URL") or "").strip().rstrip("/")
    if not base:
        return None
    body = json.dumps({"path": path, "args": args or {}, "format": "json"}).encode()
    req = urllib.request.Request(f"{base}/api/query", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            out = json.loads(r.read())
        return out.get("value") if isinstance(out, dict) else out
    except Exception as e:  # noqa: BLE001
        log.debug("convex query failed: %s", e)
        return None


def hydrate() -> dict | None:
    """Rebuild local state from Convex.

    Render's disk is ephemeral: without this, every deploy drops the demo back
    to its seed and real usage is lost. Convex is the only store that outlives a
    deploy, so on boot we rebuild from it. Returns None when Convex is absent or
    unreachable, and the caller keeps whatever is on disk.
    """
    rows = _query("corrections:history", {"limit": 500})
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r.get("correctionId", 0))
    corrections = [{
        "id": r.get("correctionId"),
        "ts": r.get("ts", ""),
        "agent_said": r.get("agentSaid", ""),
        "user_wanted": r.get("userWanted", ""),
        "situation": r.get("situation", ""),
        "cluster": r.get("cluster", ""),
        "recurrence": r.get("recurrence", 0),
        "lane": r.get("lane", ""),
        "rationale": r.get("rationale", ""),
        "confidence": r.get("confidence", 0.0),
        "artifact": r.get("artifact") or {},
    } for r in rows]
    clusters: dict[str, int] = {}
    for c in corrections:
        clusters[c["cluster"]] = clusters.get(c["cluster"], 0) + 1
    last = rows[-1]
    return {
        "corrections": corrections,
        "clusters": clusters,
        "context_tokens": last.get("contextTokens", 0),
        "if_all_context": last.get("ifAllContext", 0),
        "queue_depth": 0,
        "adapter_version": None,
    }


def record(row: dict, context_tokens: int, if_all_context: int) -> None:
    """Mirror one stored correction. Returns immediately; never raises."""
    if not _url():
        return
    payload = {
        "correctionId": int(row.get("id", 0)),
        "ts": str(row.get("ts", "")),
        "agentSaid": str(row.get("agent_said", ""))[:2000],
        "userWanted": str(row.get("user_wanted", ""))[:2000],
        "situation": str(row.get("situation", ""))[:2000],
        "cluster": str(row.get("cluster", "")),
        "recurrence": int(row.get("recurrence", 0)),
        "lane": str(row.get("lane", "")),
        "rationale": str(row.get("rationale", ""))[:2000],
        "confidence": float(row.get("confidence", 0.0)),
        "artifact": row.get("artifact") or {},
        "contextTokens": int(context_tokens),
        "ifAllContext": int(if_all_context),
    }
    threading.Thread(target=_post, args=(payload,), daemon=True).start()
