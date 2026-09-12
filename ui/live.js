// One conversation. The routing machinery appears only when a correction
// is detected -- the fork is a moment in the chat, not a permanent board.

const $ = (id) => document.getElementById(id);
const log = $("log");
const THRESHOLD = 3;

const LANES = [
  ["code",    "a function it can't get wrong"],
  ["weights", "part of how it thinks — free to use"],
  ["context", "a note it re-reads every time"],
];

let messages = [];
let busy = false;

function setConn(mode, label) {
  $("conn").className = "dot" + (mode ? " " + mode : "");
  $("connlbl").textContent = label;
}

function scroll() {
  requestAnimationFrame(() => log.scrollTo({ top: log.scrollHeight, behavior: "smooth" }));
}

function addMsg(who, text) {
  const el = document.createElement("div");
  el.className = "msg " + (who === "you" ? "you" : "bot");
  el.innerHTML = `<div class="who">${who === "you" ? "YOU" : "AGENT"}</div>
                  <div class="body"></div>`;
  el.querySelector(".body").textContent = text;
  log.appendChild(el);
  scroll();
  return el;
}

// the routing moment ---------------------------------------------------------

function addRoute() {
  const el = document.createElement("div");
  el.className = "route pending";
  el.innerHTML = `
    <div class="top">
      <span class="k">CORRECTION</span>
      <span class="t">deciding where this belongs…</span>
      <span class="n"></span>
    </div>
    <div class="fork">
      ${LANES.map(([l, d]) => `
        <div class="opt" data-l="${l}">
          <span class="n">${l.toUpperCase()}</span>
          <span class="d">${d}</span>
        </div>`).join("")}
    </div>`;
  log.appendChild(el);
  scroll();
  return el;
}

function resolveRoute(el, alloc, state) {
  el.classList.remove("pending");
  if (!alloc || alloc.error) {
    el.querySelector(".top .t").textContent = alloc?.error || "routing failed";
    return;
  }
  el.querySelector(".top .t").textContent = "routed";
  el.querySelector(`.opt[data-l=${alloc.lane}]`)?.classList.add("win");

  const why = document.createElement("div");
  why.className = "why";
  why.innerHTML = `<span class="mono">WHY</span>`;
  why.appendChild(document.createTextNode(alloc.rationale || ""));
  el.appendChild(why);

  // recurrence dots, from the cluster this correction landed in
  const rows = state?.corrections || [];
  const last = rows[rows.length - 1];
  const count = last ? (state.clusters || {})[last.cluster] || 0 : 0;
  if (count) {
    const n = el.querySelector(".top .n");
    const shown = Math.max(THRESHOLD, Math.min(count, 5));
    for (let i = 0; i < shown; i++) {
      const d = document.createElement("span");
      d.className = "rdot" + (i < count ? (i >= THRESHOLD - 1 ? " on" : " seen") : "");
      n.appendChild(d);
    }
    n.title = `${count}× this kind of correction`;
  }
  scroll();
}

// sending --------------------------------------------------------------------

async function send(text) {
  if (busy || !text.trim()) return;
  busy = true;
  $("go").disabled = true;
  document.querySelector(".hint")?.remove();

  addMsg("you", text);
  messages.push({ role: "user", content: text });
  setConn("busy", "thinking");

  const thinking = addMsg("agent", "…");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    const d = await res.json();

    if (!res.ok) {
      thinking.querySelector(".body").textContent = d.message || d.error || "that didn't work";
      thinking.querySelector(".body").style.color = "#e06c6c";
      setConn("", "error");
      return;
    }

    // a correction fires the pipeline: show the fork BEFORE the reply
    if (d.was_correction) {
      thinking.remove();
      const route = addRoute();
      await new Promise((r) => setTimeout(r, 450));
      resolveRoute(route, d.allocation, d.state);
      addMsg("agent", d.reply);
    } else {
      thinking.querySelector(".body").textContent = d.reply;
    }

    messages.push({ role: "assistant", content: d.reply });
    setConn("live", "live");
  } catch (err) {
    thinking.querySelector(".body").textContent = String(err);
    setConn("", "offline");
  } finally {
    busy = false;
    $("go").disabled = false;
    $("msg").focus();
  }
}

$("bar").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("msg").value;
  $("msg").value = "";
  send(v);
});

$("reset").addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  setConn("busy", "restoring");
  try {
    await fetch("/reset", { method: "POST" });
    messages = [];
    log.innerHTML = "";
    setConn("live", "live");
  } catch {
    setConn("", "offline");
  } finally {
    busy = false;
  }
});

log.addEventListener("click", (e) => {
  const b = e.target.closest(".try");
  if (b) { $("msg").value = b.dataset.t; $("msg").focus(); }
});

fetch("/state.json", { cache: "no-store" })
  .then((r) => (r.ok ? setConn("live", "live") : setConn("", "offline")))
  .catch(() => setConn("", "offline"));
