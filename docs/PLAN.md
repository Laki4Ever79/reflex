# Build plan

Three lanes, three people, one pinned contract. Nobody waits on anybody.

**Run `python harness.py` constantly.** It probes every lane through the one entry point
that lane owes the other two. Green on your own row means you can push. Somebody else's
row being red is their problem — never work around it.

---

## Aleksa — allocator + promotion gate + integration

The two pieces where a decision is architectural, and the two that decide whether the
product is real.

**1. `allocator/allocate.py` — `allocate(Correction) -> Allocation`**

grok-4.6 at `https://api.x.ai/v1/chat/completions` (OpenAI-compatible, `XAI_API_KEY`),
system prompt from `allocator/prompt.txt`, JSON response, parsed strictly into the
dataclasses.

On malformed output: retry once, then raise. **No fallback to context.** A safe-looking
fallback sends every ambiguous case to context, the token line rises like everyone
else's, and the product quietly stops being true while still appearing to work.

**2. `allocator/cli.py`** — pipe a correction in, see lane + rationale + confidence out.
This is how you iterate the prompt, and prompt quality *is* product quality here.

**3. The twenty labels.** Label twenty real corrections by hand, then run the same twenty
through the allocator. **Agreement rate is the first real metric and a number for the
video.** Nobody else can do this — it needs someone who remembers which corrections
were real.

**4. `lanes/weights/gate.py` — `evaluate(incumbent, challenger) -> GateVerdict`**

Held-out corrections, score both adapters, promote only if the challenger wins. Return a
verdict either way. **A rejected cycle is a demo asset** — make sure a rejection is
visible rather than silent.

**5. Integration.** You own the seam. When two lanes disagree, you decide.

**Done when:** twenty corrections route, the agreement rate is written down, and the gate
returns verdicts for both outcomes.

**Don't:** build the dashboard, tune LoRA hyperparameters, touch anyone's lane.

---

## Lazar V — code lane, then dashboard

**1. `lanes/code/materialize.py` — `materialize(CodeArtifact) -> tool`**

grok-4.6 writes the function body. **Execute it in a Daytona sandbox via the daytona MCP,
never locally** — agent-written code running isolated is the point, and it's what makes
Daytona load-bearing rather than decorative. Validate it runs and returns before
registering it as a callable tool. Surface failures; don't swallow them.

Expose registered tools for the dashboard: name, signature, `call_when`, invoked-yet.

**2. Deploy + draft submission.** Render, via the render MCP. **Submit the entry the
moment anything runs** — resubmitting updates the same entry, so there is no reason to
wait until it's good.

**3. `lanes/context/store.py` — `store(ContextArtifact)` + `context_tokens() -> int`**

Twenty lines. Bullets with their trigger (`always` or `retrieved_on:<cue>`), loaded per
turn. The running token total is the number the closing shot plots — it lives with you
because the dashboard renders it.

**4. Dashboard (`ui/`)** — once the code lane is green. Three lanes side by side, a
correction animating into the lane it was routed to, the allocator's rationale on each
item, a recurrence counter per cluster, queue depth, current adapter version.

This is the thing being filmed. Dependency-light, no build step that can break late.

**Done when:** a correction becomes a function that ran in a sandbox and is callable, context
bullets store and count, the public URL is live, and the dashboard shows three lanes filling.

**Don't:** run generated code locally. Add a framework. Style anything before it works.

---

## Lazar J — weights lane

**Start with the GPU smoke test before anything else.** Sandbox up, `nvidia-smi`,
`pip install unsloth`, twenty steps on junk data. If GPU access needs a quota request you
need to know now, not later. **Report the result to the group the moment you have it** —
it's the only thing that can force an architecture change.

**1. `lanes/weights/synthesize.py` — `synthesize(WeightsArtifact) -> list[PreferencePair]`**

One principle in, ~12 preference pairs out, applying it across varied situations via
grok-4.6. This is what turns 20 corrections into 200+ examples. Without it a training run
on a handful of pairs won't move anything and the whole lane is theatre.

**2. `lanes/weights/train.py`** — queue pairs; at `TRAINING_QUEUE_DEPTH`, spin an
ephemeral Daytona GPU sandbox (`daytona-gpu` snapshot, `auto_delete_interval=0` or it
dies mid-run), QLoRA on Qwen3-8B 4-bit, DPO/ORPO, r=16 on q/k/v/o_proj, pull the adapter
back. **Trigger on queue depth, not a clock.**

**3. Adapter versioning.** Every adapter gets a version and a parent. Never merge into the
base — an adapter is a file you can revert, a merge is not.

**Done when:** a principle becomes twelve pairs, a queue triggers a real GPU run, and an
adapter comes back with a version number.

**Don't:** tune hyperparameters. Try to beat the base model on general quality — the
adapter owns *learned behaviours*, nothing else.

---

## Commit schedule

**Push every ~30 minutes, your own directory only.** Small commits, push immediately.
Nobody holds work locally — an unpushed branch at hour four is how integration dies.

**`contracts.py` is pinned.** Say it out loud before you touch it. Changing a shape there
blocks two other people mid-task.

**Never commit a red harness row that's yours.**

## Checkpoints

**A — one call path each.** Allocator returns a real Allocation. A CodeArtifact becomes a
function that ran in a sandbox. A principle becomes pairs. Harness: three OK rows.
*Your lane works in isolation.*

**B — end to end.** One correction goes in and the right thing happens in the right lane,
without anyone editing anything by hand. Harness all green.
*This is the moment the demo exists. Everything after is quality.*

**C — freeze.** No new features. Seed the recurrence history so the counter can hit its
threshold on camera. Rehearse the three minutes once, out loud, before recording.

If B looks unreachable, **cut the weights lane and ship two.** The routing story holds
with two lanes; it does not hold with a broken third. That call is Aleksa's and it gets
made at checkpoint B, not at 18:30.

## The one thing that ends this badly

A working system and no video. Whoever owns the video starts it before the build feels
finished, because it never will.
