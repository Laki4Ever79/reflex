# Lane briefs

One per person. Paste the brief into Cursor as the opening prompt, with the repo open.
`AGENTS.md` carries the shared rules — Cursor picks it up automatically.

**Before anything else, all three:** agree `contracts.py` out loud. It's the only thing
that crosses lane boundaries; once it's pinned nobody blocks on anybody.

---

## P1 — Allocator, context lane, dashboard

> Build the allocator in `allocator/`. It takes a `Correction` (see `contracts.py`) and
> returns an `Allocation` by calling grok-4.6 with `allocator/prompt.txt`. Parse strictly
> into the dataclasses; on a malformed response retry once, then raise — do not silently
> default to the context lane, that fallback destroys the product's claim.
>
> Then the context lane in `lanes/context/`: ACE-style structured bullets, each with a
> trigger (`always` or `retrieved_on:<cue>`), stored so the agent loads them per turn.
> Track total context tokens — that number is the one the closing shot plots.
>
> Then the dashboard in `ui/`: three lanes side by side, a correction animating into the
> lane it was routed to, the allocator's `rationale` visible on each item, a recurrence
> counter per cluster, queue depth, current adapter version. This is the thing being
> filmed — dependency-light, no build step that can break at 17:00.

**Also owns:** integration, and the video.

---

## P2 — Code lane

> Build `lanes/code/`. Input is a `CodeArtifact` from the allocator. Have grok-4.6 write
> the function body, then execute it in a Daytona sandbox via the daytona MCP — never
> locally, the point is that agent-written code runs isolated. Validate it runs and
> returns before registering it as a callable tool the agent can invoke, and surface
> failures rather than swallowing them.
>
> Registered tools need to be listed for the dashboard: name, signature, `call_when`,
> and whether it's been invoked yet.

**Also owns:** Render deploy and the draft submission. Submit as soon as anything runs —
resubmitting updates the same entry, so there's no reason to wait for it to be good.

---

## P3 — Weights lane

> Build `lanes/weights/`. Three pieces:
>
> **L2 synthesis** — take a `WeightsArtifact` (a principle, not pairs) and have grok-4.6
> generate ~12 `PreferencePair`s applying that principle across varied situations. This
> is what turns 20 corrections into 200+ examples; without it a training run won't move
> anything.
>
> **Training** — when the queue hits `TRAINING_QUEUE_DEPTH`, spin an ephemeral Daytona
> GPU sandbox via the daytona MCP (`daytona-gpu` snapshot, `auto_delete_interval=0`),
> run QLoRA on Qwen3-8B 4-bit with DPO/ORPO, r=16 on q/k/v/o_proj, pull the adapter back.
> Trigger on queue depth, not a clock.
>
> **Promotion gate** — hold out a slice of corrections. Score incumbent adapter vs
> challenger on them. Promote only if the challenger wins; otherwise discard and keep
> the incumbent. Return a `GateVerdict` either way — a rejection is a demo asset, so
> make sure a rejected cycle is visible rather than silent.

Lazar J — the GPU pivot

  The Daytona credentials don't include GPU. We're not changing the idea, just where training runs.

  
Ask the Daytona people at the event for GPU access first. Five minutes, costs nothing, and if it works the original architecture survives intact.
If not: free Colab or Kaggle T4, and shrink to Qwen3-1.7B. Here's the thing — we never needed live GPU. We need one training run, ever, plus maybe
a second so the promotion gate has something to reject. Those don't happen on camera. Train once, commit the adapter, and the demo shows the queue
filling and the behaviour changing.

  So your lane is: synthesize() first (one principle → ~12 preference pairs via grok — this is what turns 20 corrections into 200+ examples, without it
  a run won't move anything), then one real training run producing a versioned adapter.

  DPO/ORPO, not SFT — a correction is already a preference pair. LoRA r=16, q/k/v/o_proj. Don't tune hyperparameters.

**Start with the GPU smoke test before anything else:** sandbox up, `nvidia-smi`,
`pip install unsloth`, a 20-step run on junk data. If GPU access needs a quota request
you need to know that immediately, not at 15:00.

---

## Model selection in Cursor

**Turn Auto off for the allocator.** Auto routes to cheaper models, and the allocator's
judgement quality *is* the product's quality — a weak routing decision looks exactly
like a broken product on camera.

| Work | Model |
|---|---|
| Allocator logic, `prompt.txt` iteration, promotion gate | **Strongest available** (Claude Opus 5 class). This is the product |
| L2 synthesis, code-lane generation, training pipeline | Strong mid-tier (Sonnet 5 class) — real logic, not subtle judgement |
| Dashboard, scaffolding, glue, deploy config | Fast tier. Volume work, obvious correctness |

Note the distinction: the model *inside* the product is grok-4.6 (x.ai is the sponsor and
it's a runtime partner-tool use that gets scored). The model in Cursor is dev-phase and
scores nothing — pick it purely for build speed and quality.

---

## Gate

Twenty real corrections, hand-labelled code / weights / context.

If they fan out, the routing decision has stakes. If eighteen of twenty say *context*,
there's no policy to demonstrate — and the pitch, the demo, the differentiator and the
moat collapse together, because they're all the same claim.

The ones where you hesitated are the ones that go in the video.
