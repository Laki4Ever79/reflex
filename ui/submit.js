// Correction input for the public demo. Judges type here.
// Talks to POST /correct and POST /reset on the same origin.
(function () {
  const bar = document.createElement("form");
  bar.id = "correct-bar";
  bar.innerHTML = `
    <input id="c-said"   placeholder="What the agent said"        autocomplete="off">
    <input id="c-wanted" placeholder="What you wanted instead"    autocomplete="off" required>
    <button id="c-send" type="submit">Correct it</button>
    <button id="c-reset" type="button" title="Restore the seeded demo state">Reset</button>
    <span id="c-msg"></span>`;
  document.body.appendChild(bar);

  const msg = document.getElementById("c-msg");
  const send = document.getElementById("c-send");

  function say(text, kind) {
    msg.textContent = text;
    msg.className = kind || "";
  }

  bar.addEventListener("submit", async (e) => {
    e.preventDefault();
    const wanted = document.getElementById("c-wanted").value.trim();
    if (!wanted) return;
    send.disabled = true;
    say("routing…", "pending");
    try {
      const res = await fetch("/correct", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_said: document.getElementById("c-said").value.trim(),
          user_wanted: wanted,
          situation: "",
        }),
      });
      const d = await res.json();
      if (!res.ok) {
        say(d.message || d.error || `error ${res.status}`, "err");
      } else {
        say(`→ ${d.lane.toUpperCase()} · ${d.rationale}`, "ok");
        document.getElementById("c-said").value = "";
        document.getElementById("c-wanted").value = "";
      }
    } catch (err) {
      say(String(err), "err");
    } finally {
      send.disabled = false;
    }
  });

  document.getElementById("c-reset").addEventListener("click", async () => {
    say("restoring seeded state…", "pending");
    try {
      const res = await fetch("/reset", { method: "POST" });
      say(res.ok ? "seeded state restored" : "reset failed", res.ok ? "ok" : "err");
    } catch (err) {
      say(String(err), "err");
    }
  });
})();
