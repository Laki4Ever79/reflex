# The 3-minute video

Read it. Don't improvise. Every line below is timed and says something true.

**Before you hit record**
1. Open the live URL and let it wake — free tier sleeps, ~50s cold
2. Hit **Reset** → seeded state, `acknowledgement-as-filler` primed at 3
3. Full screen, chat on the left, pipeline visible on the right
4. Have these three lines ready to paste:
   - `Add a retry to the upload function.`
   - `You keep saying it's done without running the tests. Run the suite before telling me a change is ready.`
   - `Staging moved to stg-2.internal last week.`

---

## 0:00–0:20 · the problem

> *"Every AI coding agent learns from you by writing it down. A note, a memory,
> a rule in a file. That note then gets re-read on every single call you make,
> for the rest of the project. Agents get slower and more expensive the better
> they know you."*

**On screen:** the chat, empty, nothing else. Don't show the panel yet.

---

## 0:20–0:45 · the claim

> *"Some of what you tell it shouldn't be a note at all. Some of it should be
> code. Some of it belongs in the weights. Reflex decides which — per
> correction, live."*

**On screen:** send the first message — *Add a retry to the upload function.*
Reply streams in. Point at the panel: *"nothing fires — that's an ordinary request."*

---

## 0:45–1:35 · the correction

> *"Now I correct it. Not in a form — I just tell it off, the way you actually
> would."*

**Send:** *You keep saying it's done without running the tests...*

Let the panel run. Then read it out as it fills:

> *"It noticed that was a correction. It extracted the rule. Third time I've
> said this. And it routed it to code — because a function can guarantee it.
> Grok wrote that function, and it's running right now in a Daytona sandbox —
> agent-written code never touches our machine."*

**On screen:** sandbox ID and the return value appear. CODE counter bumps.

---

## 1:35–2:10 · the other lane

> *"Not everything can be a function."*

**Send:** *Staging moved to stg-2.internal last week.*

> *"That's a fact. Nothing can check it, it'll go stale, and it's only come up
> once — so it goes to context. Which is the expensive lane: that one gets
> re-read on every call from now on. That's the tax, and we count it."*

**On screen:** point at `carried on every call` vs `if every correction were a note`.

---

## 2:10–2:40 · it listened

**Hit Replay** — *Ask the same thing again.*

> *"Same question I asked at the start. It answers differently now, because the
> correction is in the system, not in my head."*

---

## 2:40–3:00 · the close

> *"SEAL updates weights. ACE updates context. Voyager writes tools. None of
> them asks which one a learning belongs in. We route first, then update — and
> that's why this agent gets cheaper as it learns instead of more expensive.
> It's live, the link's in the description, go correct it yourself."*

---

## If asked

**"Isn't this just Hermes / OpenClaw?"**
Two lanes and no policy — it writes memory *and* builds skills, nothing decides
which. Its PEFT skill tunes models *for* you; it never tunes itself.

**"So add fine-tuning to Hermes."**
That's the whole problem. Two destinations means you need a policy, and nobody
has one. You can't bolt on an allocator.

**"Is the weights lane real?"**
It trains and it serves — CPU inference in a Daytona sandbox, 8 seconds a call.
We don't route the demo through it because a 0.6B is worse than grok at
everything except the one thing it learned, and the cascade that picks the right
turns is what we didn't build. That's where a GPU goes.

**"How do you know the routing is any good?"**
24 real corrections from a production Serbian voice-agent project, hand-labelled,
88% agreement — stable across three runs. Two of the three disagreements were
the model being right and the human wrong.

## Never say

personalised AI for everyone · an AI trained on your data · gets better the more
you use it · a path to AGI · nobody has done this
