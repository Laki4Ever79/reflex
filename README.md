# Reflex

**Every reflex was learned once.**

Your agent re-derives the same conclusion every session, forever. You correct it, it writes a note, and the note becomes a tax you pay on every future call. Reflex routes each correction to where it actually belongs — and some of them belong in the weights.

> **System 2 once. Reflex forever.**

---

## The idea

Every self-improving agent commits to one substrate up front.
[SEAL](https://arxiv.org/abs/2506.10943) updates weights. [ACE](https://arxiv.org/abs/2510.04618) updates context.
[Voyager](https://arxiv.org/html/2602.12430v4)'s descendants write tools. [Second Me](https://github.com/mindverse/Second-Me)
funnels everything into a personal model.

**None of them asks which one a given learning belongs in.**

Reflex routes first, then updates. A correction becomes a deterministic function, a context
bullet, or training data — decided per correction, by policy.

## Why it matters

Every other personal AI gets **more expensive** the more it learns. Additive systems have one
destination, so they can only grow, and everything they remember is tokens on every future call.

Reflex gets **cheaper**, because each learning goes where it costs the least to use.

## The three lanes

Not a taxonomy — three different cost structures. That's what makes routing a real decision.

| Lane | Write cost | Read cost | Guarantee | For |
|---|---|---|---|---|
| **code** | medium | on invocation | **hard** | rules that can be checked, computed, looked up |
| **weights** | high (a GPU run) | **zero** | soft — it biases | behavioural judgement *that recurs* |
| **context** | ~zero | **recurring, forever** | soft | specific facts, rare cases, everything else |

## The policy

An ordered check, not a score. **The order is the product.**

```
1. Can a deterministic function guarantee this?          -> CODE
2. Behavioural judgement AND recurrence >= 3?            -> WEIGHTS
3. Everything else                                       -> CONTEXT
```

Two hard rules:

- **Never send to another lane what a function can guarantee.** Weights bias. Code promises.
- **Context is the lane of last resort**, not the default. Every item placed there is a tax on
  every future call, forever.

## The loop

```
user corrects the agent
        |
        v
  ALLOCATOR (grok-4.6)  ->  { lane, rationale, confidence, artifact }
        |
  +-----+------------------+---------------------------+
  v                        v                           v
CONTEXT                   CODE                      WEIGHTS
bullet -> store    Grok writes fn          principle -> L2 synthesis -> queue
                   -> Daytona sandbox                        |
                   -> registered tool          queue >= N ---+
                                                    v
                                     Daytona GPU sandbox - QLoRA
                                                    v
                                   eval vN vs vN+1 on held-out
                                                    v
                                better -> promote | worse -> discard
```

The promotion gate is not optional. Reflex mutates an assistant while nobody is watching — if a
cycle makes it worse, it has to be caught and reverted. That's also why the weights lane is LoRA
and never a merge: an adapter is a file you can revert.

## Stack

| | |
|---|---|
| Allocator + L2 synthesis + escalation tier | **grok-4.6** (x.ai) |
| Code execution, adapter training | **Daytona** sandboxes — ephemeral GPU for training, persistent GPU for inference |
| Public URL | **Render** |
| Base model | Qwen3-8B, 4-bit QLoRA, LoRA r=16 on q/k/v/o_proj |
| Objective | DPO/ORPO — a correction is natively a preference pair |

## Layout

```
contracts.py        pinned interfaces between lanes - agree before editing
allocator/          the routing decision            (P1)
lanes/context/      structured bullets              (P1)
lanes/code/         Grok writes fn -> sandbox       (P2)
lanes/weights/      synthesis -> QLoRA -> gate      (P3)
ui/                 dashboard                       (P1)
docs/DEMO.md        shot list
```

## Prior art

Every ingredient has an owner. The composition is the idea, and we say so.

| | | |
|---|---|---|
| [SEAL](https://arxiv.org/abs/2506.10943) | self-directed weight updates | weights-only; never asks whether it belongs in weights |
| [ACE](https://arxiv.org/abs/2510.04618) | evolving structured context | explicitly *"rather than weight updates"* |
| [Second Me](https://github.com/mindverse/Second-Me) | automated personal post-training | a pipeline, not a router — everything funnels to weights |
| [Hermes](https://hermes-agent.org/) | memory + auto-built skills + a PEFT skill | two lanes, no policy; its PEFT tunes models *for* you, never itself |
| [distil labs](https://www.distillabs.ai/) | small model trained to defer | per-task, B2B, one-shot — not per-user, not continual |

SEAL's own future work: *"models that not only adapt their weights but also reason about when and
how to adapt."* That's this.

## License

MIT
