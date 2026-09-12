// Live junction. Polls /state.json, posts corrections to /correct.
// The branch that lights up is the one the allocator actually chose.

const LANES = ["code", "weights", "context"];
const THRESHOLD = 3;
const $ = (id) => document.getElementById(id);

let busy = false;

function setConn(mode, label) {
  $("conn").className = "dot" + (mode ? " " + mode : "");
  $("connlbl").textContent = label;
}

function setDots(n) {
  const box = $("dots");
  box.innerHTML = "";
  const shown = Math.max(THRESHOLD, Math.min(n, 6));
  for (let i = 0; i < shown; i++) {
    const d = document.createElement("span");
    d.className = "rdot" + (i < n && i >= THRESHOLD - 1 ? " on" : "");
    if (i < n && i < THRESHOLD - 1) d.style.background = "var(--muted)";
    box.appendChild(d);
  }
}

function clearRoute() {
  LANES.forEach((l) => {
    $("b-" + l).className = "branch";
    document.querySelector(`.lane[data-l=${l}]`).classList.remove("chosen");
  });
}

function showRoute(lane) {
  clearRoute();
  $("b-" + lane).className = "branch taken " + lane;
  document.querySelector(`.lane[data-l=${lane}]`).classList.add("chosen");
}

function thinking(on) {
  $("trunk").className.baseVal = on ? "trunk busy" : "trunk";
  $("node").className.baseVal = on ? "node thinking" : "node";
  $("nodetext").textContent = on ? "deciding…" : "which lane?";
  if (on) clearRoute();
}

// ---- render the latest correction from state --------------------------------

function renderLatest(state) {
  const rows = state.corrections || [];
  if (!rows.length) return;
  const r = rows[rows.length - 1];

  $("quote").textContent = "“" + r.user_wanted + "”";
  $("why").textContent = r.rationale || "";
  showRoute(r.lane);

  const count = (state.clusters || {})[r.cluster] || 0;
  setDots(count);
  const hot = r.lane === "weights";
  $("rnote").className = "rnote" + (hot ? " hot" : "");
  $("rnote").textContent =
    count >= THRESHOLD
      ? `${count}× — enough to be worth learning`
      : `${count}× — not yet worth training on`;

  // lane footers: what each lane is actually holding
  const by = { code: 0, weights: 0, context: 0 };
  rows.forEach((x) => { if (by[x.lane] !== undefined) by[x.lane]++; });
  $("f-code").textContent = by.code
    ? `${by.code} function${by.code > 1 ? "s" : ""} written`
    : "nothing here yet";
  $("f-weights").textContent = by.weights
    ? `${by.weights} principle${by.weights > 1 ? "s" : ""} queued for training`
    : "nothing here yet";
  const tok = state.context_tokens || 0;
  $("f-context").textContent = by.context
    ? `${by.context} note${by.context > 1 ? "s" : ""}` + (tok ? ` · ${tok} tokens every call` : "")
    : "nothing here yet";
}

async function poll() {
  if (busy) return;
  try {
    const res = await fetch("/state.json", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    setConn("live", "live");
    renderLatest(await res.json());
  } catch {
    setConn("", "offline");
  }
}

// ---- submitting -------------------------------------------------------------

$("bar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const wanted = $("wanted").value.trim();
  if (!wanted || busy) return;

  busy = true;
  $("go").disabled = true;
  setConn("busy", "asking the allocator");
  thinking(true);
  $("quote").textContent = "“" + wanted + "”";
  $("why").textContent = "…";
  $("hint").className = "hint";

  try {
    const res = await fetch("/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_said: $("said").value.trim(),
        user_wanted: wanted,
        situation: "",
      }),
    });
    const d = await res.json();
    thinking(false);

    if (!res.ok) {
      $("hint").className = "hint err";
      $("hint").textContent = d.message || d.error || "that didn't work";
      $("why").textContent = "";
      setConn("", "error");
    } else {
      $("said").value = "";
      $("wanted").value = "";
      if (d.state) renderLatest(d.state);
      setConn("live", "live");
    }
  } catch (err) {
    thinking(false);
    $("hint").className = "hint err";
    $("hint").textContent = String(err);
    setConn("", "offline");
  } finally {
    busy = false;
    $("go").disabled = false;
  }
});

$("reset").addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  setConn("busy", "restoring");
  try {
    const res = await fetch("/reset", { method: "POST" });
    const d = await res.json();
    if (d.state) renderLatest(d.state);
    setConn("live", "live");
  } catch {
    setConn("", "offline");
  } finally {
    busy = false;
  }
});

document.querySelectorAll(".try").forEach((b) => {
  b.addEventListener("click", () => {
    $("said").value = b.dataset.s || "";
    $("wanted").value = b.dataset.w || "";
    $("wanted").focus();
  });
});

poll();
setInterval(poll, 2500);
