"""Resident inference process. Uploaded and executed INSIDE the Daytona sandbox
by inference.py — never run this locally.

Loads the base model + the current adapter ONCE, then serves prompts read as
JSON lines from stdin, writing JSON responses as lines to stdout. Kept alive
across chat messages so the model doesn't get reloaded per message.

Protocol (line-delimited JSON, both directions):
  in:  {"prompt": "..."}
  out: {"response": "..."}   on success
       {"error": "..."}      on a generation failure for that one prompt
"""

import argparse
import json
import os
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--base-model", required=True)
ap.add_argument("--adapter-dir", default=None)
ap.add_argument("--cpus", type=int, default=2)
args = ap.parse_args()

# Same thread-oversubscription fix as _remote_train.py: must happen before
# torch/numpy import, or the library sizes its thread pool off the host's
# core count instead of this sandbox's actual cgroup CPU limit.
os.environ["OMP_NUM_THREADS"] = str(args.cpus)
os.environ["MKL_NUM_THREADS"] = str(args.cpus)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

torch.set_num_threads(args.cpus)

tokenizer = AutoTokenizer.from_pretrained(args.base_model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(args.base_model, dtype=torch.bfloat16)

if args.adapter_dir:
    from peft import PeftModel

    model = PeftModel.from_pretrained(model, args.adapter_dir)

model.eval()

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def generate(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    # Qwen3 defaults to emitting a <think>...</think> reasoning block before
    # the actual reply, which eats the token budget and looks broken in a
    # chat UI. enable_thinking=False turns it off at the template level;
    # the regex strip below is a safety net for tokenizer versions where
    # that kwarg isn't wired through.
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    raw = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return _THINK_BLOCK.sub("", raw).strip()


print("READY", flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        prompt = json.loads(line)["prompt"]
        response = generate(prompt)
        print(json.dumps({"response": response}), flush=True)
    except Exception as e:  # noqa: BLE001 - one bad prompt must not kill the resident process
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), flush=True)
