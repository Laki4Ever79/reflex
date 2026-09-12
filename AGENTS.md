# Working on Reflex

Read this before writing code. It is the whole design decision set — the reasoning
behind it was settled before the build started and should not be re-derived.

## What this is

Reflex routes each correction a user makes to an AI agent into the lane where that
learning costs least to use: **code**, **weights**, or **context**.

Everything else that self-improves commits to one substrate. SEAL updates weights.
ACE updates context. Voyager writes tools. None of them asks which one a given
learning belongs in. **The routing decision is the product.** Everything else in
this repo is scaffolding around it.

## The policy — do not weaken this

An ordered check, not a score. The order is the product.

```
1. Can a deterministic function guarantee this?          -> CODE
2. Behavioural judgement AND recurrence >= 3?            -> WEIGHTS
3. Everything else                                       -> CONTEXT
```

Two invariants:

- **Never send to another lane what a function can guarantee.** Weights bias.
  Code promises. Prefer the promise.
- **Context is the lane of last resort, not the default.** Every item placed there
  is a token tax on every future call, forever. If context grows unboundedly, the
  product's entire claim is false.

If you find yourself writing a fallback that routes ambiguous cases to context
"to be safe" — stop. That fallback is the failure mode, not the safety net.

## contracts.py is pinned

`contracts.py` is the boundary between three people working in parallel. Do not
change a shape in it as a side effect of working on a lane. Changing it blocks
two other people.

## Locked decisions

| | |
|---|---|
| Allocator brain | `grok-4.6` via x.ai. Also does L2 synthesis and serves as escalation tier |
| Base model | Qwen3-8B, 4-bit QLoRA |
| LoRA config | r=16, target `q_proj,k_proj,v_proj,o_proj`. Do not tune today |
| Objective | DPO/ORPO, not SFT. A correction is natively a preference pair |
| Training | Ephemeral Daytona GPU sandbox. `auto_delete_interval=0` or it dies mid-run |
| Inference | Persistent Daytona GPU sandbox, 4-bit base + adapter |
| Public URL | Render |
| Weights updates | LoRA adapters only. **Never merge.** An adapter is a file you can revert |
| Emission | Harness-agnostic; Hermes memory + skill formats are the one working target |

## Not in scope — do not build these

Voice. Multi-user. Auth. User accounts. The shared/collective router (architecture
slide only — it trains on routing *decisions*, never user content). Anything that
is not the routing visualization or a lane.

## MCP servers available

- **daytona** — sandbox create/exec/upload/download, preview URLs, GPU sandboxes
- **render** — deploy the public URL
- **convex**, **wonder** — available, not currently required

Use them directly rather than writing provisioning scripts by hand.

## Two things the demo must be able to show

These are requirements, not polish. Build so they are reachable:

1. **One counterintuitive routing call** — something that looks like an instruction
   and correctly becomes code. If every decision on screen looks obvious, the
   allocator reads as an if-statement.
2. **A recurrence counter hitting its threshold on camera.** Requires seeded prior
   corrections to exist, or the weights lane can never fire and the GPU never boots.

## The promotion gate is not optional

A new adapter must beat its predecessor on held-out corrections or it is discarded.
We mutate someone's assistant while they aren't watching; if a cycle makes it worse
that has to be caught. A demo where every cycle improves looks salted — showing a
**rejection** is more convincing than showing a success.

## Style

Python 3.11+, dataclasses over dicts at boundaries, type hints on anything crossing
a lane. No framework unless it earns its place. Keep the dashboard dependency-light —
it is the thing being filmed, and a build step that breaks at 17:00 costs the video.

## Setup

```bash
pip install -r requirements.txt
```

`daytona` is a real PyPI package and is required by the code lane. The Daytona MCP
in your editor is a separate thing — having the MCP does not install the SDK, and
the harness will show the code lane red until you `pip install`.
