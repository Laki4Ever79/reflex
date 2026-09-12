// Chat directly with the current adapter. Talks to POST /chat on the same
// origin. First message pays for sandbox warmup (dependency install + model
// load) and can take a few minutes; every message after that is fast.
(function () {
  const toggle = document.createElement("button");
  toggle.id = "chat-toggle";
  toggle.type = "button";
  toggle.textContent = "chat with the agent";
  document.body.appendChild(toggle);

  const panel = document.createElement("div");
  panel.id = "chat-panel";
  panel.innerHTML = `
    <div class="chat-head">
      <strong>talk to the current adapter</strong>
      <span id="chat-adapter-label">v—</span>
    </div>
    <div id="chat-log"><p class="chat-empty-hint">first reply can take a few minutes while the sandbox warms up — every one after that is quick.</p></div>
    <div class="chat-input-row">
      <textarea id="chat-input" rows="1" placeholder="Say something to the agent…"></textarea>
      <button id="chat-send" type="button">Send</button>
    </div>`;
  document.body.appendChild(panel);

  const log = document.getElementById("chat-log");
  const input = document.getElementById("chat-input");
  const send = document.getElementById("chat-send");
  const adapterLabel = document.getElementById("chat-adapter-label");

  toggle.addEventListener("click", () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) input.focus();
  });

  function addMsg(text, cls) {
    const hint = log.querySelector(".chat-empty-hint");
    if (hint) hint.remove();
    const el = document.createElement("div");
    el.className = `chat-msg ${cls}`;
    el.textContent = text;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  async function sendPrompt() {
    const prompt = input.value.trim();
    if (!prompt) return;
    input.value = "";
    send.disabled = true;
    addMsg(prompt, "user");
    const pending = addMsg("thinking…", "agent pending");

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data = await res.json();
      pending.remove();
      if (!res.ok) {
        addMsg(data.message || data.error || `error ${res.status}`, "error");
      } else {
        addMsg(data.response, "agent");
      }
    } catch (err) {
      pending.remove();
      addMsg(String(err), "error");
    } finally {
      send.disabled = false;
      input.focus();
    }
  }

  send.addEventListener("click", sendPrompt);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });

  // Reuse the dashboard's own poll: if app.js exposes the last adapter
  // version on the topbar, mirror it here so the chat header always
  // matches "which adapter am I actually talking to".
  setInterval(() => {
    const v = document.getElementById("adapter-version");
    if (v) adapterLabel.textContent = v.textContent;
  }, 2000);
})();
