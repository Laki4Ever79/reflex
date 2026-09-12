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
from allocator.chat import detect, reply
from allocator.store import STATE_PATH, allocate_and_store, load
from contracts import Correction
from lanes.weights.inference import chat as run_chat

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


@app.post("/chat")
async def chat(req: Request):
    """One turn with the agent.

    If the user's message is a correction, it goes down the pipeline in the
    same breath - the demo's whole point is that a correction is something you
    SAY, not something you file. The response carries both the agent's reply
    and, when one happened, the routing decision.
    """
    ip = _client_ip(req)
    if not _rate_ok(ip):
        return JSONResponse(
            {"error": "rate_limited",
             "message": f"{RATE_LIMIT} messages per {RATE_WINDOW // 60} minutes. "
                        "Every turn costs real model calls."},
            status_code=429,
        )

    body = await req.json()
    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": "empty", "message": "Say something first."},
                            status_code=400)
    messages = [
        {"role": m.get("role"), "content": str(m.get("content") or "")[:MAX_FIELD * 3]}
        for m in messages[-12:]
        if m.get("role") in ("user", "assistant")
    ]

    allocation = None
    detected = {"is_correction": False}
    try:
        detected = detect(messages)
        if detected["is_correction"] and detected["user_wanted"]:
            a = allocate_and_store(
                Correction(
                    agent_said=detected["agent_said"],
                    user_wanted=detected["user_wanted"],
                    situation=detected["situation"],
                    recurrence=0,
                )
            )
            allocation = {"lane": a.lane, "rationale": a.rationale,
                          "confidence": a.confidence}
    except AllocationError as e:
        allocation = {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        allocation = {"error": f"{type(e).__name__}: {e}"}

    try:
        text = reply(messages, load())
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": "agent_failed", "message": f"{type(e).__name__}: {e}"},
                            status_code=502)

    return {
        "reply": text,
        "was_correction": bool(detected.get("is_correction")),
        "allocation": allocation,
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


@app.post("/chat")
def chat_endpoint(req: Request, body: dict):
    """Talk to the current adapter directly. Sync def on purpose - run_chat()
    blocks (it polls a Daytona sandbox), and a sync route runs in Starlette's
    threadpool instead of the event loop, so a slow generation doesn't stall
    /state.json polling for everyone else watching the dashboard."""
    ip = _client_ip(req)
    if not _rate_ok(ip):
        return JSONResponse(
            {"error": "rate_limited",
             "message": f"{RATE_LIMIT} requests per {RATE_WINDOW // 60} minutes "
                        "(shared with /correct - both cost real model calls)."},
            status_code=429,
        )

    prompt = (body.get("prompt") or "").strip()[:MAX_FIELD]
    if not prompt:
        return JSONResponse(
            {"error": "empty", "message": "Say something to the agent."}, status_code=400
        )

    try:
        response = run_chat(prompt)
    except TimeoutError as e:
        return JSONResponse({"error": "timeout", "message": str(e)}, status_code=504)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            {"error": "inference_failed", "message": f"{type(e).__name__}: {e}"},
            status_code=500,
        )
    return {"response": response}


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
