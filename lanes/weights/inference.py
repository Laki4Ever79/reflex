"""Chat with the current adapter, served from one persistent Daytona sandbox.

Lazily creates the sandbox and starts a resident inference process on the
first call; every call after that just writes a prompt to its stdin and
reads the response back — no reload per message. Kept alive for the life of
this process (server.py). If server.py restarts (e.g. a Render redeploy),
the next chat call re-warms a fresh sandbox automatically.
"""

import json
import os
import threading
import time

from dotenv import load_dotenv

from daytona import CreateSandboxFromImageParams, Daytona, Resources, SessionExecuteRequest

from lanes.weights.train import BASE_MODEL, PIP_PACKAGES, PIP_TORCH_CMD, SANDBOX_CPUS, latest_adapter

load_dotenv()

IMAGE = "python:3.11-slim"
SESSION_ID = "infer"
READY_TIMEOUT = 600  # first call pays for deps install + model download
RESPONSE_TIMEOUT = 120

_lock = threading.Lock()
_state = {"sandbox": None, "cmd_id": None, "read_pos": 0}


def _weights_dir():
    from pathlib import Path

    return Path(__file__).parent


def _upload_dir(sandbox, local_dir, remote_dir):
    for path in local_dir.rglob("*"):
        if path.is_file():
            remote_path = f"{remote_dir}/{path.relative_to(local_dir)}"
            sandbox.fs.upload_file(str(path), remote_path)


def _ensure_ready():
    """Creates the sandbox + resident process on first use. Caller holds _lock."""
    if _state["sandbox"] is not None:
        return

    daytona = Daytona()
    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image=IMAGE,
            auto_delete_interval=0,
            resources=Resources(cpu=SANDBOX_CPUS, memory=8, disk=10),
        )
    )

    sandbox.fs.upload_file(str(_weights_dir() / "_infer_resident.py"), "_infer_resident.py")

    adapter = latest_adapter()
    adapter_remote_dir = None
    if adapter is not None:
        from pathlib import Path

        adapter_remote_dir = "adapter"
        _upload_dir(sandbox, Path(adapter.path), adapter_remote_dir)

    install_torch = sandbox.process.exec(PIP_TORCH_CMD, timeout=1200)
    if install_torch.exit_code != 0:
        sandbox.delete()
        raise RuntimeError(f"torch install failed: {install_torch.result}")
    install = sandbox.process.exec(f"pip install -q {PIP_PACKAGES} peft", timeout=1200)
    if install.exit_code != 0:
        sandbox.delete()
        raise RuntimeError(f"dependency install failed: {install.result}")

    sandbox.process.create_session(SESSION_ID)
    cmd = f"python3 -u _infer_resident.py --base-model {BASE_MODEL} --cpus {SANDBOX_CPUS}"
    if adapter_remote_dir:
        cmd += f" --adapter-dir {adapter_remote_dir}"
    result = sandbox.process.execute_session_command(
        SESSION_ID, SessionExecuteRequest(command=cmd, run_async=True)
    )
    cmd_id = result.cmd_id

    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        logs = sandbox.process.get_session_command_logs(SESSION_ID, cmd_id)
        if "READY" in (logs.stdout or ""):
            _state["sandbox"] = sandbox
            _state["cmd_id"] = cmd_id
            _state["read_pos"] = len(logs.stdout)
            return
        cmd_status = sandbox.process.get_session_command(SESSION_ID, cmd_id)
        if cmd_status.exit_code is not None:
            sandbox.delete()
            raise RuntimeError(f"resident process exited early: {logs.stderr or logs.stdout}")
        time.sleep(2)

    sandbox.delete()
    raise RuntimeError("resident process did not report READY in time")


def chat(prompt: str) -> str:
    with _lock:
        _ensure_ready()
        sandbox = _state["sandbox"]
        cmd_id = _state["cmd_id"]

        sandbox.process.send_session_command_input(
            SESSION_ID, cmd_id, json.dumps({"prompt": prompt}) + "\n"
        )

        deadline = time.time() + RESPONSE_TIMEOUT
        while time.time() < deadline:
            logs = sandbox.process.get_session_command_logs(SESSION_ID, cmd_id)
            stdout = logs.stdout or ""
            new = stdout[_state["read_pos"]:]
            for line in new.splitlines():
                line = line.strip()
                if not line or line == "READY":
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "prompt" in data:
                    continue  # the sandbox PTY echoes our stdin write back into the log
                _state["read_pos"] = len(stdout)
                if "error" in data:
                    raise RuntimeError(f"generation failed: {data['error']}")
                return data["response"]
            time.sleep(0.5)

        raise TimeoutError("no response from the resident inference process in time")
