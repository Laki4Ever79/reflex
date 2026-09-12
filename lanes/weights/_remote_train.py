"""DPO training run. Uploaded and executed INSIDE the Daytona sandbox by train.py —
never run this locally.

Expects, in the sandbox working directory:
  - pairs.json  (list of {"prompt", "chosen", "rejected"})

Produces:
  - ./adapter_out/  (LoRA adapter, loadable with peft.PeftModel.from_pretrained)
"""

import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("--base-model", required=True)
ap.add_argument("--max-steps", type=int, default=-1)
ap.add_argument("--cpus", type=int, default=2)
args = ap.parse_args()

# Must happen before torch/numpy import: the sandbox's cgroup CPU limit isn't what
# these libraries see when they pick a default thread count, so they oversubscribe
# to the HOST's core count and thrash on a shared, contended node. Pin explicitly.
os.environ["OMP_NUM_THREADS"] = str(args.cpus)
os.environ["MKL_NUM_THREADS"] = str(args.cpus)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

torch.set_num_threads(args.cpus)

tokenizer = AutoTokenizer.from_pretrained(args.base_model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(args.base_model, dtype=torch.bfloat16)

# Locked LoRA shape (AGENTS.md: "r=16, target q_proj,k_proj,v_proj,o_proj. Do not
# tune today") — unaffected by the CPU/GPU swap, same adapter shape either way.
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

with open("pairs.json") as f:
    raw = json.load(f)

dataset = Dataset.from_list(
    [{"prompt": p["prompt"], "chosen": p["chosen"], "rejected": p["rejected"]} for p in raw]
)

trainer = DPOTrainer(
    model=model,
    args=DPOConfig(
        output_dir="dpo_output",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=2,
        num_train_epochs=3,
        max_steps=args.max_steps,
        max_length=512,
        learning_rate=5e-5,
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        bf16=False,
    ),
    train_dataset=dataset,
    processing_class=tokenizer,
)

trainer.train()
model.save_pretrained("adapter_out")
tokenizer.save_pretrained("adapter_out")
print("DONE_TRAINING")
