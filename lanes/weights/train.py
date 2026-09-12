"""Weights lane training: queue -> ephemeral Daytona sandbox -> QLoRA/DPO -> adapter.

TEMPORARY CPU DEVIATION FROM AGENTS.md's LOCKED DECISIONS: the team's Daytona
organization has no paid GPU credits yet (`Organization doesn't have GPU credits` on
sandbox create), so this runs the identical pipeline — same LoRA shape, same DPO
objective — on a CPU sandbox with a smaller Qwen3 checkpoint instead of the locked
Qwen3-8B + `daytona-gpu` snapshot. Flagged to the group per PLAN.md ("report the
result the moment you have it"). To restore the locked path once credits land:
  - IMAGE -> the `daytona-gpu` snapshot
  - add resources=Resources(gpu=1, gpu_type=[...]) to the CreateSandboxFromImageParams
  - BASE_MODEL -> "Qwen/Qwen3-8B", and give _remote_train.py back 4-bit quantization
Nothing else about the flow changes.
"""

import json
import os
import sys
import tarfile
import time
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from daytona import CreateSandboxFromImageParams, Daytona, Resources, SessionExecuteRequest

from contracts import Adapter, PreferencePair
from lanes.weights import queue

load_dotenv()

BASE_MODEL = "Qwen/Qwen3-0.6B"  # CPU-friendly stand-in for the locked Qwen3-8B GPU target
IMAGE = "python:3.11-slim"
SANDBOX_CPUS = 2  # keep in sync with Resources(cpu=...) below — torch is told this exactly
# torch needs its own CPU wheel index; installed separately so that index doesn't
# also get searched (and fail) for the plain-PyPI packages below.
PIP_TORCH_CMD = "pip install -q torch --index-url https://download.pytorch.org/whl/cpu"
PIP_PACKAGES = "transformers peft trl accelerate datasets"

WEIGHTS_DIR = Path(__file__).parent
REMOTE_TRAIN_SCRIPT = WEIGHTS_DIR / "_remote_train.py"
ADAPTERS_DIR = WEIGHTS_DIR / "adapters"
REGISTRY_PATH = ADAPTERS_DIR / "registry.json"


def _load_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    return json.loads(REGISTRY_PATH.read_text())


def latest_adapter() -> Adapter | None:
    entries = _load_registry()
    return Adapter(**entries[-1]) if entries else None


def _next_version() -> tuple[int, int | None]:
    entries = _load_registry()
    if not entries:
        return 1, None
    parent = entries[-1]["version"]
    return parent + 1, parent


def _run_and_stream(sandbox, session_id, command, poll_interval=5):
    sandbox.process.create_session(session_id)
    result = sandbox.process.execute_session_command(
        session_id, SessionExecuteRequest(command=command, run_async=True)
    )
    cmd_id = result.cmd_id
    printed = 0
    while True:
        cmd = sandbox.process.get_session_command(session_id, cmd_id)
        logs = sandbox.process.get_session_command_logs(session_id, cmd_id)
        stdout = logs.stdout or ""
        if len(stdout) > printed:
            sys.stdout.write(stdout[printed:])
            sys.stdout.flush()
            printed = len(stdout)
        if cmd.exit_code is not None:
            stderr = (logs.stderr or "").strip()
            if stderr:
                print(f"\n--- stderr ({session_id}) ---\n{stderr}", file=sys.stderr)
            return cmd.exit_code
        time.sleep(poll_interval)


def train(pairs: list[PreferencePair], max_steps: int = -1) -> Adapter:
    """Runs one DPO training cycle on `pairs` in an ephemeral Daytona sandbox and
    registers the resulting adapter. `max_steps` exists for the smoke test — a real
    queue-triggered run leaves it at -1 (epoch-bounded)."""
    if not os.environ.get("DAYTONA_API_KEY"):
        raise RuntimeError("DAYTONA_API_KEY not set")
    if not pairs:
        raise ValueError("train() called with zero pairs")

    daytona = Daytona()
    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image=IMAGE,
            auto_delete_interval=0,
            # defaults aren't enough for torch + transformers + the model cache/weights
            resources=Resources(cpu=SANDBOX_CPUS, memory=8, disk=10),
        )
    )
    try:
        sandbox.fs.upload_file(str(REMOTE_TRAIN_SCRIPT), "_remote_train.py")
        sandbox.fs.upload_file(
            json.dumps([asdict(p) for p in pairs]).encode(), "pairs.json"
        )

        install_torch = sandbox.process.exec(PIP_TORCH_CMD, timeout=1200)
        if install_torch.exit_code != 0:
            raise RuntimeError(f"torch install failed: {install_torch.result}")

        install = sandbox.process.exec(f"pip install -q {PIP_PACKAGES}", timeout=1200)
        if install.exit_code != 0:
            raise RuntimeError(f"dependency install failed: {install.result}")

        train_cmd = (
            f"python _remote_train.py --base-model {BASE_MODEL} "
            f"--max-steps {max_steps} --cpus {SANDBOX_CPUS}"
        )
        exit_code = _run_and_stream(sandbox, "training", train_cmd)
        if exit_code != 0:
            raise RuntimeError(f"training failed, exit code {exit_code}")

        pack = sandbox.process.exec("tar czf adapter.tar.gz adapter_out", timeout=120)
        if pack.exit_code != 0:
            raise RuntimeError(f"packaging failed: {pack.result}")

        content = sandbox.fs.download_file("adapter.tar.gz")
    finally:
        sandbox.delete()

    version, parent = _next_version()
    local_dir = ADAPTERS_DIR / f"v{version}"
    local_dir.mkdir(parents=True, exist_ok=True)
    archive_path = local_dir / "adapter.tar.gz"
    archive_path.write_bytes(content)
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(local_dir)
    archive_path.unlink()

    adapter = Adapter(
        version=version, path=str(local_dir / "adapter_out"), trained_on=len(pairs), parent=parent
    )
    entries = _load_registry()
    entries.append(asdict(adapter))
    REGISTRY_PATH.write_text(json.dumps(entries, indent=2))
    return adapter


def maybe_train() -> Adapter | None:
    """Called after every enqueue. Fires a real training run only at queue depth —
    trigger is TRAINING_QUEUE_DEPTH, never a clock."""
    if not queue.ready():
        return None
    pairs = queue.drain()
    return train(pairs)
