/**
 * reflex dashboard — polls a JSON snapshot of pipeline state and renders
 * three lanes. No build step, no framework: this file IS the deploy.
 *
 * ---------------------------------------------------------------------
 * STATE SHAPE THIS FILE EXPECTS (mirrors contracts.ReflexState, but this
 * exact JSON shape is NOT part of the pinned contract — contracts.py only
 * pins LaneState.items as a generic `list`. This is the assumed item shape
 * until whoever wires the real integration (the seam — Aleksa) confirms or
 * changes it. If it changes, only the `render*` functions below need edits.
 *
 * {
 *   "code":    { "items": [Item, ...], "context_tokens": 0 },
 *   "weights": { "items": [Item, ...], "context_tokens": 0 },
 *   "context": { "items": [Item, ...], "context_tokens": 212 },
 *   "adapter": { "version": 3, "parent": 2, "trained_on": 140 } | null,
 *   "queue_depth": 12
 * }
 *
 * Item = {
 *   "id": "unique-string",       // stable id, used to detect "is this new"
 *   "rationale": "one sentence from the allocator",
 *   "recurrence": 4,             // corrections seen in this cluster so far
 *   "ts": "2026-09-12T10:31:00Z" // optional, ISO timestamp
 * }
 * ---------------------------------------------------------------------
 */

const CONFIG = {
  // server.py registers GET /state.json before mounting ui/ as static
  // files, so this resolves to the live endpoint (backed by
  // allocator/store.py) whenever server.py is what's serving this page.
  // Falls back to fabricated data if that request fails for any reason
  // (page opened as a bare static file, backend down, ...) — so the
  // board is never just blank.
  STATE_URL: "./state.json",
  POLL_MS: 1500,
  MAX_ITEMS_PER_LANE: 6,
  WEIGHTS_QUEUE_THRESHOLD: 50, // mirrors contracts.TRAINING_QUEUE_DEPTH
};

const LANES = ["code", "weights", "context"];

// ids we've already animated in, per lane — so we only play the "landing"
// animation once per item, not on every poll.
const seenIds = { code: new Set(), weights: new Set(), context: new Set() };

// ---------------------------------------------------------------------
// mock fallback — keeps the board alive for rehearsal when there's no
// real backend yet. Clearly labelled as mock in the status bar.
// ---------------------------------------------------------------------

const MOCK_RATIONALES = {
  code: [
    "deterministic fix, safe to promise as a tool",
    "agent needs a reusable check, not a one-off reply",
    "same failure mode recurring — worth a real function",
  ],
  weights: [
    "a style preference, not a fact — bias the model instead",
    "recurs across unrelated situations, generalizes well",
    "tone correction, applies broadly",
  ],
  context: [
    "one-off fact, cheap to just remember",
    "low recurrence, not worth a training cycle",
    "environment detail, changes rarely",
  ],
};

let mockState = {
  code: { items: [], context_tokens: 0 },
  weights: { items: [], context_tokens: 0 },
  context: { items: [], context_tokens: 0 },
  adapter: { version: 1, parent: null, trained_on: 84 },
  queue_depth: 6,
};
let mockTick = 0;

function advanceMock() {
  mockTick += 1;

  // Every couple of ticks, route a new fake correction somewhere.
  if (mockTick % 2 === 0) {
    const lane = LANES[Math.floor(Math.random() * LANES.length)];
    const pool = MOCK_RATIONALES[lane];
    const rationale = pool[Math.floor(Math.random() * pool.length)];
    const item = {
      id: `mock-${lane}-${mockTick}`,
      rationale,
      recurrence: Math.floor(Math.random() * 6),
      ts: new Date().toISOString(),
    };
    mockState[lane].items.unshift(item);
    mockState[lane].items = mockState[lane].items.slice(0, CONFIG.MAX_ITEMS_PER_LANE);

    if (lane === "context") {
      mockState.context.context_tokens += 4 + Math.floor(Math.random() * 8);
    }
    if (lane === "weights") {
      mockState.queue_depth = Math.min(
        CONFIG.WEIGHTS_QUEUE_THRESHOLD,
        mockState.queue_depth + Math.floor(Math.random() * 3)
      );
      if (mockState.queue_depth >= CONFIG.WEIGHTS_QUEUE_THRESHOLD) {
        mockState.adapter = {
          version: mockState.adapter.version + 1,
          parent: mockState.adapter.version,
          trained_on: mockState.adapter.trained_on + CONFIG.WEIGHTS_QUEUE_THRESHOLD,
        };
        mockState.queue_depth = 0;
      }
    }
  }

  return mockState;
}

// ---------------------------------------------------------------------
// real backend shape -> the per-lane shape render() expects
//
// server.py / allocator/store.py persist ONE flat "corrections" list
// (each row tagged with a "lane"), not three pre-split lane buckets, and
// track a single adapter_version int rather than an {version,parent,...}
// object. That's the seam the comment at the top of this file warned
// about. Adjust HERE if allocator/store.py's shape changes again — the
// render* functions below should never need to know the wire format.
// ---------------------------------------------------------------------
function normalizeState(raw) {
  const byLane = { code: [], weights: [], context: [] };
  for (const row of raw.corrections ?? []) {
    if (!(row.lane in byLane)) continue; // failed/unknown allocation - skip, don't crash the board
    byLane[row.lane].push({
      id: String(row.id),
      rationale: row.rationale,
      recurrence: row.recurrence,
      ts: row.ts,
    });
  }
  LANES.forEach((lane) => byLane[lane].reverse()); // newest first, matches MAX_ITEMS_PER_LANE slicing

  return {
    code: { items: byLane.code, context_tokens: 0 },
    weights: { items: byLane.weights, context_tokens: 0 },
    context: { items: byLane.context, context_tokens: raw.context_tokens ?? 0 },
    adapter: raw.adapter_version != null ? { version: raw.adapter_version } : null,
    queue_depth: raw.queue_depth ?? 0,
  };
}

// ---------------------------------------------------------------------
// fetching real state, with mock fallback
// ---------------------------------------------------------------------

async function fetchState() {
  try {
    const res = await fetch(CONFIG.STATE_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`state.json responded ${res.status}`);
    const raw = await res.json();
    setConnStatus("live");
    return normalizeState(raw);
  } catch (err) {
    setConnStatus("mock");
    return advanceMock();
  }
}

function setConnStatus(mode) {
  const dot = document.getElementById("conn-status");
  const label = document.getElementById("conn-label");
  dot.className = `status-dot status-${mode}`;
  label.textContent =
    mode === "live"
      ? "connected to live pipeline"
      : "mock data — not connected to a live pipeline";
}

// ---------------------------------------------------------------------
// rendering
// ---------------------------------------------------------------------

function renderTopbar(state) {
  document.getElementById("adapter-version").textContent = state.adapter
    ? `v${state.adapter.version}`
    : "—";
  document.getElementById("queue-depth").textContent = state.queue_depth ?? 0;
  document.getElementById("weights-threshold").textContent = CONFIG.WEIGHTS_QUEUE_THRESHOLD;
}

function laneColor(lane) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--lane-${lane}`).trim();
}

function makeItemEl(item, lane) {
  const el = document.createElement("div");
  el.className = "item";
  el.dataset.id = item.id;
  const recurrence = item.recurrence ?? 0;
  el.innerHTML = `
    <div class="item-rationale">${escapeHtml(item.rationale ?? "")}</div>
    <div class="item-meta">
      <span class="recurrence-badge">×${recurrence}</span>
      <span>${item.ts ? new Date(item.ts).toLocaleTimeString() : ""}</span>
    </div>
  `;
  return el;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/** Play the "arriving correction" animation: a chip appears in the shared
 * inbox, then launches toward the destination lane and fades as the real
 * item card fades/slides into place in that lane's list. One orchestrated
 * moment, not a per-card hover effect. */
function animateArrival(item, lane) {
  const inbox = document.getElementById("inbox");
  const laneEl = document.querySelector(`.lane[data-lane="${lane}"]`);
  if (!inbox || !laneEl) return;

  const chip = document.createElement("div");
  chip.className = "chip";
  chip.style.setProperty("--chip-color", laneColor(lane));
  chip.textContent = item.rationale ?? lane;
  inbox.appendChild(chip);

  const inboxRect = chip.getBoundingClientRect();
  const laneRect = laneEl.getBoundingClientRect();
  const dx = laneRect.left + laneRect.width / 2 - (inboxRect.left + inboxRect.width / 2);
  const dy = laneRect.top - inboxRect.top + 40;

  requestAnimationFrame(() => {
    chip.style.transform = `translate(calc(-50% + ${dx}px), ${dy}px) scale(0.6)`;
    chip.classList.add("launch");
  });

  setTimeout(() => chip.remove(), 650);
}

function renderLane(lane, laneState) {
  const container = document.getElementById(`${lane}-items`);
  const items = (laneState.items ?? []).slice(0, CONFIG.MAX_ITEMS_PER_LANE);

  if (items.length === 0) {
    container.innerHTML = `<p class="empty-hint">nothing routed here yet</p>`;
  } else if (container.querySelector(".empty-hint")) {
    container.innerHTML = "";
  }

  const newOnes = items.filter((it) => !seenIds[lane].has(it.id));

  // Rebuild the list in order, reusing existing DOM nodes where possible
  // so we don't re-trigger the fade-in on items already on screen.
  const existingIds = new Set(Array.from(container.children).map((c) => c.dataset && c.dataset.id));
  container.innerHTML = "";
  items.forEach((item) => {
    const el = makeItemEl(item, lane);
    container.appendChild(el);
    if (!existingIds.has(item.id) || newOnes.includes(item)) {
      requestAnimationFrame(() => el.classList.add("in"));
    } else {
      el.classList.add("in");
    }
  });

  newOnes.forEach((item) => {
    seenIds[lane].add(item.id);
    animateArrival(item, lane);
  });

  const statEl = document.getElementById(`${lane}-stat`);
  if (lane === "code") statEl.textContent = items.length;
  if (lane === "context") statEl.textContent = laneState.context_tokens ?? 0;
  if (lane === "weights") statEl.textContent = "—"; // queue depth shown top bar instead
}

function render(state) {
  renderTopbar(state);
  LANES.forEach((lane) => renderLane(lane, state[lane] ?? { items: [], context_tokens: 0 }));
}

// ---------------------------------------------------------------------
// main loop
// ---------------------------------------------------------------------

async function tick() {
  const state = await fetchState();
  render(state);
}

tick();
setInterval(tick, CONFIG.POLL_MS);
