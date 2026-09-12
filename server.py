"""Public interactive Reflex demo.

    uvicorn server:app --host 0.0.0.0 --port $PORT

Serves the dashboard and accepts corrections from anyone who opens the URL.
Judges will click this, so three things matter beyond the happy path:

  reset       five people adding corrections destroys the seeded recurrence
              state, and with it the demo's best frame. /reset restores it.
  rate limit  every correction costs two grok calls against a fixed credit
              pool. This endpoint is on the public internet.
  degrade     an allocator failure returns an error the UI can render. It
              never falls back to a lane - that would void the whole claim.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from allocator.allocate import AllocationError
from allocator.store import STATE_PATH, allocate_and_store, load
from contracts import Correction

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
SEED_CSV = ROOT / "demo_seed.csv"
SEED_SNAPSHOT = ROOT / "state.seed.json"

# public endpoint, fixed credit pool
RATE_LIMIT = 15          # corrections
RATE_WINDOW = 600        # per 10 minutes, per IP
MAX_FIELD = 400          # chars

_hits: dict[str, deque] = defaultdict(deque)

app = FastAPI(title="Reflex")


def _client_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "?")


def _rate_ok(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return False
    q.append(now)
    return True


@app.get("/state.json")
def state():
    return JSONResponse(load(), headers={"Cache-Control": "no-store"})


@app.post("/correct")
async def correct(req: Request):
    ip = _client_ip(req)
    if not _rate_ok(ip):
        return JSONResponse(
            {"error": "rate_limited",
             "message": f"{RATE_LIMIT} corrections per {RATE_WINDOW // 60} minutes. "
                        "Every correction costs real model calls."},
            status_code=429,
        )

    body = await req.json()
    said = (body.get("agent_said") or "").strip()[:MAX_FIELD]
    wanted = (body.get("user_wanted") or "").strip()[:MAX_FIELD]
    situation = (body.get("situation") or "").strip()[:MAX_FIELD]

    if not wanted:
        return JSONResponse(
            {"error": "empty", "message": "Tell the agent what you wanted instead."},
            status_code=400,
        )

    try:
        a = allocate_and_store(
            Correction(agent_said=said, user_wanted=wanted,
                       situation=situation, recurrence=0)
        )
    except AllocationError as e:
        # never fall back to a lane: a default would silently void the claim
        return JSONResponse(
            {"error": "allocation_failed", "message": str(e)}, status_code=502
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            {"error": "server_error", "message": f"{type(e).__name__}: {e}"},
            status_code=500,
        )

    return {
        "lane": a.lane,
        "rationale": a.rationale,
        "confidence": a.confidence,
        "state": load(),
    }


@app.post("/reset")
def reset():
    """Restore the seeded demo state. Public on purpose - anyone can unbreak it."""
    if SEED_SNAPSHOT.exists():
        shutil.copy(SEED_SNAPSHOT, STATE_PATH)
        return {"ok": True, "source": "snapshot", "state": load()}
    if not SEED_CSV.exists():
        return JSONResponse({"error": "no_seed"}, status_code=500)
    subprocess.run(
        [sys.executable, "-m", "allocator.seed", "--reset", str(SEED_CSV)],
        cwd=ROOT, check=False, capture_output=True, timeout=300,
    )
    return {"ok": True, "source": "replayed", "state": load()}


@app.get("/health")
def health():
    s = load()
    return {
        "ok": True,
        "corrections": len(s.get("corrections", [])),
        "clusters": s.get("clusters", {}),
        "xai_key": bool(os.environ.get("XAI_API_KEY")),
    }


@app.get("/")
def index():
    return FileResponse(UI / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=UI), name="ui")
