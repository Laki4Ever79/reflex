// Chat on the left, pipeline on the right. /chat and /observe fire together:
// the answer never waits on the routing, and the routing is visible while it runs.

const $ = (id) => document.getElementById(id);
const log = $("log"), stages = $("stages");

let messages = [];
let busy = false;
let lastAsk = null;      // the request that preceded a correction — for replay
let pendingAsk = null;

function scroll(el) {
  requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }));
}

function addMsg(who, text, cls) {
  const el = document.createElement("div");
  el.className = "msg " + (who === "you" ? "you" : "bot") + (cls ? " " + cls : "");
  el.innerHTML = `<div class="who">${who === "you" ? "YOU" : "AGENT"}</div><div class="body"></div>`;
  if (text === null) {
    el.querySelector(".body").innerHTML = `<span class="typing"><i></i><i></i><i></i></span>`;
  } else {
    el.querySelector(".body").textContent = text;
  }
  log.appendChild(el);
  scroll(log);
  return el;
}

// ---- pipeline panel --------------------------------------------------------

function clearStages() {
  stages.innerHTML = "";
  stages.className = "";
}

function tintPanel(lane) { stages.className = "as-" + lane; }

function stage(state, title, detail, opts = {}) {
  const el = document.createElement("div");
  el.className = "stage " + state;
  el.innerHTML = `<span class="pip"></span><div class="sbody"><div class="st"></div></div>`;
  el.querySelector(".st").textContent = title;
  const body = el.querySelector(".sbody");
  if (detail) {
    const d = document.createElement("div");
    d.className = "sd" + (opts.mono ? " code" : "");
    d.textContent = detail;
    body.appendChild(d);
  }
  if (opts.html) body.insertAdjacentHTML("beforeend", opts.html);
  stages.appendChild(el);
  scroll(stages);
  return el;
}

function dotsHtml(count, threshold) {
  const shown = Math.max(threshold, Math.min(count, 5));
  let h = '<div class="dots">';
  for (let i = 0; i < shown; i++) {
    h += `<span class="rdot ${i < count ? (i >= threshold - 1 ? "on" : "seen") : ""}"></span>`;
  }
  return h + "</div>";
}

function setTax(state) {
  if (!state) return;
  const now = state.context_tokens || 0;
  const all = state.if_all_context || 0;
  $("tok-now").textContent = now + " tok";
  $("tok-all").textContent = all + " tok";
  $("tok-fill").style.width = all ? Math.round((now / all) * 100) + "%" : "0%";
}

const _prev = { code: null, weights: null, context: null };

function totalsOf(state) {
  const t = { code: 0, weights: 0, context: 0 };
  (state?.corrections || []).forEach((c) => { if (t[c.lane] !== undefined) t[c.lane]++; });
  return t;
}

function countUp(el, from, to) {
  if (from === to) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 450;
  (function step(now) {
    const k = Math.min(1, (now - t0) / dur);
    el.textContent = Math.round(from + (to - from) * k);
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

function setTotals(t) {
  if (!t) return;
  const total = (t.code || 0) + (t.weights || 0) + (t.context || 0);
  for (const lane of ["code", "weights", "context"]) {
    const now = t[lane] ?? 0;
    const was = _prev[lane];
    const num = $("t-" + lane);
    const tile = num.parentElement;

    countUp(num, was == null ? now : was, now);
    const bar = document.getElementById("f-" + lane + "-bar");
    if (bar) bar.style.width = total ? Math.round((now / total) * 100) + "%" : "0%";

    // a lane that just gained one should be impossible to miss
    if (was != null && now > was) {
      const pop = $("p-" + lane);
      pop.textContent = "+" + (now - was);
      pop.classList.remove("go");
      void pop.offsetWidth;
      pop.classList.add("go");
      tile.classList.add("bump");
      setTimeout(() => tile.classList.remove("bump"), 620);
    }
    _prev[lane] = now;
  }
}

function renderObserve(d) {
  clearStages();
  stage("done", "Turn observed", "checked against what the agent just said");

  if (!d.is_correction) {
    stage("miss", "Not a correction", d.error || "an ordinary request — nothing to route");
    $("pulse").className = "pulse";
    return;
  }

  stage("done", "Correction detected", d.rule);

  if (d.error) {
    stage("miss", "Routing failed", d.error);
    $("pulse").className = "pulse";
    return;
  }

  stage("done", `Cluster · ${d.cluster}`,
        `${d.count}× this kind of correction`,
        { html: dotsHtml(d.count, d.threshold) });

  tintPanel(d.lane);
  stage("done", "Routed",
        d.rationale,
        { html: `<div><span class="lane-pill ${d.lane}">${d.lane.toUpperCase()}</span></div>` });

  if (d.made) stage("done", "Produced", d.made, { mono: d.lane === "code" });

  // the code lane actually runs — boot a sandbox and show what came back
  if (d.lane === "code") runSandbox();

  setTotals(d.totals);
  setTax(d.state);
  $("pulse").className = "pulse";
  if (lastAsk) $("replay").classList.add("show");
}

async function runSandbox() {
  const st = stage("run", "Running it in a Daytona sandbox…",
                   "agent-written code never executes on our machine");
  $("pulse").className = "pulse on";
  try {
    const res = await fetch("/materialize", { method: "POST" });
    const d = await res.json();
    if (!res.ok) {
      st.className = "stage miss";
      st.querySelector(".st").textContent = "Sandbox failed";
      st.querySelector(".sd").textContent = d.message || d.error || "unknown";
    } else {
      st.className = "stage done";
      st.querySelector(".st").textContent = "Ran in a Daytona sandbox";
      st.querySelector(".sd").textContent =
        (d.sandbox_id ? d.sandbox_id.slice(0, 12) + " · " : "") +
        (d.returned != null ? "returned " + d.returned : "validated");
      if (d.implementation) {
        const c = document.createElement("div");
        c.className = "sd code";
        c.textContent = d.implementation.trim();
        st.querySelector(".sbody").appendChild(c);
      }
    }
  } catch (err) {
    st.className = "stage miss";
    st.querySelector(".sd").textContent = String(err);
  } finally {
    $("pulse").className = "pulse";
    scroll(stages);
  }
}

// ---- sending ---------------------------------------------------------------

async function send(text, isReplay) {
  if (busy || !text.trim()) return;
  busy = true;
  $("go").disabled = true;
  $("replay").classList.remove("show");
  document.querySelector(".hint")?.remove();
  document.getElementById("hero")?.classList.add("gone");  // pitch yields to the product

  const sentText = text;
  addMsg("you", text);
  messages.push({ role: "user", content: text });
  const bubble = addMsg("agent", null, isReplay ? "corrected" : "");

  clearStages();
  stage("run", "Observing the turn…", "does this correct what the agent just said?");
  $("pulse").className = "pulse on";

  const payload = JSON.stringify({ messages });
  const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: payload };

  // pipeline runs alongside — the answer never waits on it
  const observed = fetch("/observe", opts).then((r) => r.json()).catch((e) => ({
    is_correction: false, error: String(e),
  }));

  const body = bubble.querySelector(".body");
  let acc = "";
  try {
    const res = await fetch("/chat/stream", opts);
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      body.textContent = j.message || j.error || `error ${res.status}`;
      body.style.color = "#e06c6c";
    } else {
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      body.textContent = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        body.textContent = acc;
        scroll(log);
      }
      messages.push({ role: "assistant", content: acc });
      pendingAsk = acc ? sentText : pendingAsk;
    }
  } catch (err) {
    body.textContent = String(err);
  } finally {
    busy = false;
    $("go").disabled = false;
    $("msg").focus();
  }

  const d = await observed;
  renderObserve(d);
  if (d.is_correction) {
    // the request BEFORE the correction is what replay re-asks
    const prior = messages.filter((m) => m.role === "user");
    lastAsk = prior.length >= 2 ? prior[prior.length - 2].content : null;
    if (lastAsk) $("replay").classList.add("show");
    const mine = [...log.querySelectorAll(".msg.you")].pop();
    if (mine && d.lane) {
      mine.classList.add("corrected", "lane-" + d.lane);
      const t = document.createElement("span");
      t.className = "tagline";
      t.textContent = "\u2192 " + d.lane.toUpperCase();
      mine.appendChild(t);
    }
  } else {
    lastAsk = pendingAsk;
  }
}

$("bar").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("msg").value;
  $("msg").value = "";
  send(v);
});

$("replay").addEventListener("click", () => {
  if (lastAsk) send(lastAsk, true);
});

$("reset").addEventListener("click", async () => {
  if (busy) return;
  // shared state: one person's reset wipes everyone's corrections
  if (!confirm("Reset wipes every correction made since the demo started — for everyone on this link. Continue?")) return;
  busy = true;
  try {
    const res = await fetch("/reset", { method: "POST" });
    const d = await res.json().catch(() => ({}));
    messages = []; lastAsk = null; pendingAsk = null;
    log.innerHTML = "";
    clearStages();
    // the server has already rolled back — show what it rolled back TO
    if (d.state) {
      _prev.code = _prev.weights = _prev.context = null;  // a drop must not fire the bump
      setTotals(totalsOf(d.state));
      setTax(d.state);
    }
    stages.innerHTML =
      '<div class="idle">Every turn is watched.<br>Nothing fires unless you correct the agent.</div>';
    $("replay").classList.remove("show");
  } finally { busy = false; }
});

log.addEventListener("click", (e) => {
  const b = e.target.closest(".try");
  if (b) { $("msg").value = b.dataset.t; $("msg").focus(); }
});

fetch("/state.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((s) => {
    setTotals(totalsOf(s));
    setTax(s);
  })
  .catch(() => {});
