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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from allocator.allocate import AllocationError
from allocator.chat import detect, reply, reply_stream
from allocator.store import STATE_PATH, allocate_and_store, load
from contracts import WEIGHTS_RECURRENCE_THRESHOLD, Correction
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


def _clean(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [
        {"role": m.get("role"), "content": str(m.get("content") or "")[:MAX_FIELD * 3]}
        for m in raw[-12:]
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
    ]


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
    """The agent's reply, and nothing else. ONE model call, so it comes back fast.

    Correction detection and routing run separately via /observe, fired by the
    browser at the same moment - the pipeline is background work and should not
    make the user wait for an answer.
    """
    ip = _client_ip(req)
    if not _rate_ok(ip):
        return JSONResponse(
            {"error": "rate_limited",
             "message": f"{RATE_LIMIT} messages per {RATE_WINDOW // 60} minutes."},
            status_code=429,
        )
    body = await req.json()
    messages = _clean(body.get("messages"))
    if not messages:
        return JSONResponse({"error": "empty", "message": "Say something first."}, status_code=400)
    try:
        return {"reply": reply(messages, load())}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": "agent_failed", "message": f"{type(e).__name__}: {e}"},
                            status_code=502)


@app.post("/chat/stream")
async def chat_stream(req: Request):
    """Same reply, streamed. The wait becomes legible instead of dead."""
    ip = _client_ip(req)
    if not _rate_ok(ip):
        return JSONResponse(
            {"error": "rate_limited",
             "message": f"{RATE_LIMIT} messages per {RATE_WINDOW // 60} minutes."},
            status_code=429,
        )
    body = await req.json()
    messages = _clean(body.get("messages"))
    if not messages:
        return JSONResponse({"error": "empty", "message": "Say something first."}, status_code=400)

    state = load()

    def gen():
        try:
            for piece in reply_stream(messages, state):
                yield piece
        except Exception as e:  # noqa: BLE001
            yield f"\n[agent failed: {type(e).__name__}]"

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "no-store",
                                      "X-Accel-Buffering": "no"})


@app.post("/observe")
async def observe(req: Request):
    """The background pipeline: did that turn correct the agent, and where does it go?

    Returns the stages the side panel renders, so the work is visible rather
    than implied - detection, the extracted rule, the cluster and its count,
    the lane, and the artifact that was produced.
    """
    body = await req.json()
    messages = _clean(body.get("messages"))
    if not messages:
        return {"is_correction": False}

    try:
        d = detect(messages)
    except Exception as e:  # noqa: BLE001
        return {"is_correction": False, "error": f"{type(e).__name__}: {e}"}

    if not (d["is_correction"] and d["user_wanted"]):
        return {"is_correction": False}

    try:
        c = Correction(agent_said=d["agent_said"], user_wanted=d["user_wanted"],
                       situation=d["situation"], recurrence=0)
        a = allocate_and_store(c)
    except AllocationError as e:
        return {"is_correction": True, "rule": d["user_wanted"], "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"is_correction": True, "rule": d["user_wanted"],
                "error": f"{type(e).__name__}: {e}"}

    state = load()
    rows = state.get("corrections", [])
    cluster = getattr(c, "cluster", "") or (rows[-1]["cluster"] if rows else "")
    totals = {"code": 0, "weights": 0, "context": 0}
    for r in rows:
        if r["lane"] in totals:
            totals[r["lane"]] += 1

    art = rows[-1]["artifact"] if rows else {}
    if a.lane == "code":
        made = art.get("name", "") + "()"
    elif a.lane == "weights":
        made = art.get("principle", "")
    else:
        made = art.get("bullet", "")

    return {
        "is_correction": True,
        "rule": d["user_wanted"],
        "cluster": cluster,
        "count": (state.get("clusters", {}) or {}).get(cluster, 0),
        "threshold": WEIGHTS_RECURRENCE_THRESHOLD,
        "lane": a.lane,
        "rationale": a.rationale,
        "confidence": a.confidence,
        "made": made,
        "totals": totals,
        "state": state,
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
