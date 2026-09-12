# Demo

Surface: **a coding agent.** It happens to be working on this repo — stated once, in passing.

## Recursion rule

The demo must read correctly if you assume it's editing *any* codebase. The self-reference is a
detail the technical judges will enjoy noticing, never a premise the video depends on.
**If it needs explaining, cut it.**

## Three minutes

| | |
|---|---|
| **0:00–0:20** | An agent config after months of "learning" — bloated, all prose. Every line is a token tax on every future call. |
| **0:20–0:45** | The claim: some things shouldn't be written down. Some should be code. Some should be in the weights. Name the three destinations. |
| **0:45–1:45** | **The demo.** Three corrections, live, routed three ways. Each artifact appears: a bullet, a Python function in a sandbox, a pair in the training queue. |
| **1:45–2:20** | The sleep cycle. GPU boots, QLoRA runs, adapter out, eval gate. **Show a rejection if you have one** — it proves the gate isn't theatre. |
| **2:20–2:45** | Proof: the agent handles all three unaided. Point at where each one lives. |
| **2:45–3:00** | Context tokens per turn, over cycles. Theirs rises. Ours doesn't. Two lines, no narration. |

## Two things the demo must contain

**One counterintuitive routing call.** Something that looks like an instruction and is correctly
made into code — *"always run the tests before saying done"* is a hook, not a prompt line. If every
decision on screen looks obvious, the allocator reads as an if-statement and the whole thing looks
like plumbing.

**A recurrence counter reaching its threshold on camera.** *"Third time you've corrected this"* is
the most convincing frame available. It needs prior corrections to exist — seed a handful of real
ones, or the weights lane can't fire and the GPU story never appears.

## Language

**Never say:** personalized AI for everyone · an AI trained on your data · gets better the more you
use it · self-hosted personal assistant · a path to AGI

**Say:** every reflex was learned once · System 2 once, reflex forever · they picked a lane, we pick
the lane · memory is rent, weights are equity · never put in weights what a function can guarantee ·
Grok is the judgement layer

"AGI" is a capability claim and invites a fight you can't win in three minutes. "System 2 once,
reflex forever" is a mechanism claim and survives scrutiny.

## The two answers that matter

**"Isn't this just Hermes / OpenClaw?"**
Hermes has two lanes and no policy — it writes memory *and* builds skills, but nothing decides
which. Its PEFT skill fine-tunes models *for* you; it never fine-tunes itself. Two lanes and no
policy versus three lanes and a policy.

**"So just add fine-tuning to Hermes."**
That's the whole problem. Two places to put a learning means you need a policy, and nobody has one.
You can't bolt on an allocator. The allocator *is* the thing.

## Owners

| | |
|---|---|
| **P1** | allocator · context lane · dashboard · **integration** · **video** |
| **P2** | code lane: Grok writes fn → Daytona sandbox → registered tool · **deploy + draft submission** |
| **P3** | weights lane: L2 synthesis → queue → GPU sandbox → QLoRA → promotion gate |

Deploy and video are named owners because they're what teams drop. Submit a draft entry as soon as
anything runs — resubmitting updates the same entry.
