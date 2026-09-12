# Submission requirements

Checked against the event rules. Three of these are disqualifiers, not polish.

## Hard requirements

| | Status | Owner |
|---|---|---|
| Public repo | **done** — github.com/Laki4Ever79/reflex | — |
| Open source licence | **done** — MIT | — |
| **Deployed public URL** — localhost is rejected | **NOT DONE** | Lazar V |
| **~3 minute video** | **NOT DONE** | Aleksa |
| **Submitted entry** | **NOT DONE** | Lazar V |
| Team of 1–3 | done | — |
| Only hackathon-day work judged | done — everything here is from today | — |

## Three things to do immediately, before they're earned

All three are insurance. None of them require the product to work.

**1. Deploy a placeholder now.** A Render page that says nothing but *Reflex* satisfies
"deployed public URL" and then gets updated all day. This removes the single largest
disqualification risk in ten minutes, and it proves the deploy path works while there's
still time to debug it. Debugging a first deploy at 18:00 is how teams lose.

**2. Submit the entry now.** Resubmitting **updates the same entry** — there is no
penalty for submitting something rough and no reward for waiting. If everything goes
wrong later, you still have a submission.

**3. Record a rough video as soon as anything runs end to end.** Not the good one. The
insurance one. Then re-record when it's better. A team with a mediocre video beats a team
with a great build and no video, every single time, and the second team always believed
they had more time than they did.

## What actually earns points

Five criteria, averaged. Innovation is primary.

**Partner tools score at runtime, not build time.** This is the part most teams get wrong.
Cursor, Grok Bot and Wispr Flow are dev-phase — everyone used them, they score nothing.
What counts is partner tools inside the architecture:

- **x.ai** — grok-4.6 is the allocator's judgement layer, synthesises training pairs, and
  serves as the escalation tier. Runtime, central, not decoration.
- **Daytona** — sandboxes execute agent-written code. **Make this visible in the demo.**
  Since the GPU pivot, the code lane is now the Daytona case; if sandbox execution is
  hidden behind an abstraction, the strongest partner-tool claim disappears from view.
- **Render** — the public URL.

Say these in the video as *architecture*, never as credits.

**Clarity is our weakest criterion.** The idea is abstract and nothing in the code fixes
that — only the demo does. Budget time for it like it's a feature.

## Things not to say

"Personalized AI for everyone" · "an AI trained on your data" · "gets better the more you
use it" · "a path to AGI" · "nobody has done this"

Every ingredient here has a well-known owner. The composition is the idea, and saying so
is stronger than claiming novelty — especially in front of a judge who knows the field.

## The two answers to have ready

**"Isn't this just Hermes / OpenClaw?"** — Hermes has two lanes and no policy. It writes
memory *and* builds skills, but nothing decides which. Its PEFT skill fine-tunes models
*for* you; it never fine-tunes itself. Two lanes and no policy versus three lanes and a
policy.

**"So just add fine-tuning to Hermes."** — That's the whole problem. Two places to put a
learning means you need a policy, and nobody has one. You can't bolt on an allocator.
The allocator *is* the thing.
