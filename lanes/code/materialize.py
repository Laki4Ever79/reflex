"""Code lane — turn a CodeArtifact into a validated, callable tool.

Owes the other two lanes exactly one entry point:
    materialize(CodeArtifact) -> tool

Nothing runs locally. Ever. The implementation string on a CodeArtifact was
written upstream (by the allocator, via grok-4.6) — that's untrusted,
agent-generated code, and it only ever executes inside an ephemeral Daytona
sandbox. That isolation is the entire point of the code lane, not an
implementation detail to skip while iterating.
"""

import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

# Dodaje korenski direktorijum projekta (reflex) u Python putanju
sys.path.append(str(Path(__file__).resolve().parents[2]))

from daytona import (
    CreateSandboxFromSnapshotParams,
    Daytona,
    DaytonaError,
)

from contracts import CodeArtifact

DEBUG = True  # flip to False once this stops needing eyes on it
 
 
def _log(msg: str) -> None:
    if DEBUG:
        print(f"[code.materialize] {msg}")
 
 
# --------------------------------------------------------------------------
# what gets registered and what the dashboard reads
# --------------------------------------------------------------------------
 
@dataclass
class Tool:
    name: str
    signature: str
    call_when: str
    implementation: str
    invoked: bool = False
    sandbox_id: str | None = None
    validated_return: str | None = None  # repr() of what it returned during validation
 
    def __call__(self, *args, **kwargs):
        """A registered tool is a promise that it ran in Daytona once — real
        invocation must go through the same sandbox path again, never a local
        eval/exec shortcut. Not wired yet; raise loud rather than silently
        running untrusted code on this machine."""
        raise NotImplementedError(
            f"{self.name}: calling a materialized tool must re-execute it in "
            "a Daytona sandbox — no local execution path exists on purpose."
        )
 
 
_REGISTRY: dict[str, Tool] = {}
 
 
# --------------------------------------------------------------------------
# validation helpers
# --------------------------------------------------------------------------
 
def _takes_no_required_args(signature: str) -> bool:
    """'tests_pass() -> bool' -> True, 'send_email(to, subject) -> bool' -> False.
    Best-effort parse of the declared signature string — good enough to decide
    whether validation can safely auto-invoke the function with zero args."""
    try:
        args_part = signature.split("(", 1)[1].split(")", 1)[0]
    except IndexError:
        _log(f"couldn't parse signature {signature!r} — treating as needing args")
        return False
    return args_part.strip() == ""
 
 
def _build_probe_script(artifact: CodeArtifact, auto_invoke: bool) -> str:
    """The only code that actually runs inside the sandbox: define the
    function from artifact.implementation, then either call it (zero-arg
    case) or just prove it defines cleanly. Prints one JSON line as the
    verdict so the host side has something structured to parse.
 
    Built by joining whole lines rather than dedent-ing a single f-string —
    artifact.implementation is itself multi-line, already-valid top-level
    Python (e.g. "def f():\\n    return True\\n"), and splicing a multi-line
    value into the middle of a dedent-then-strip pipeline corrupts its
    indentation relative to the surrounding scaffold. Concatenating it as
    its own top-level block sidesteps that entirely.
    """
    call_line = (
        f"__result = {artifact.name}()"
        if auto_invoke
        else "__result = '<not auto-invoked: signature takes arguments>'"
    )
    lines = [
        "import json, traceback",
        "",
        artifact.implementation.rstrip("\n"),
        "",
        "try:",
        f'    assert callable({artifact.name}), "{artifact.name} is not callable after exec"',
        f"    {call_line}",
        '    print(json.dumps({"ok": True, "result": repr(__result)}))',
        "except Exception:",
        '    print(json.dumps({"ok": False, "error": traceback.format_exc()}))',
    ]
    return "\n".join(lines)
 
 
# --------------------------------------------------------------------------
# the entry point
# --------------------------------------------------------------------------
 
def materialize(artifact: CodeArtifact) -> Tool:
    _log(f"materialize() called — name={artifact.name!r} signature={artifact.signature!r}")
 
    if not artifact.implementation or not artifact.implementation.strip():
        raise ValueError(f"{artifact.name}: empty implementation — nothing to run")
 
    auto_invoke = _takes_no_required_args(artifact.signature)
    _log(f"auto-invoke during validation: {auto_invoke}")
 
    daytona = Daytona()  # reads DAYTONA_API_KEY / DAYTONA_API_URL / DAYTONA_TARGET from env
    sandbox = None
    try:
        _log("creating ephemeral sandbox …")
        sandbox = daytona.create(
            CreateSandboxFromSnapshotParams(
                language="python",
                ephemeral=True,
                auto_stop_interval=5,    # minutes idle before it stops itself
                auto_delete_interval=0,  # delete immediately once stopped
            )
        )
        _log(f"sandbox up — id={sandbox.id}")
 
        script = _build_probe_script(artifact, auto_invoke)
        _log("running probe script in sandbox …")
        response = sandbox.process.code_run(script, timeout=30)
 
        if response.exit_code != 0:
            raise RuntimeError(
                f"{artifact.name}: sandbox exited {response.exit_code} — {response.result}"
            )
 
        lines = [ln for ln in response.result.strip().splitlines() if ln.strip()]
        verdict = json.loads(lines[-1]) if lines else {"ok": False, "error": "no output from sandbox"}
 
        if not verdict.get("ok"):
            raise RuntimeError(f"{artifact.name}: raised inside sandbox — {verdict.get('error')}")
 
        _log(f"validated OK — returned {verdict.get('result')}")
 
        tool = Tool(
            name=artifact.name,
            signature=artifact.signature,
            call_when=artifact.call_when,
            implementation=artifact.implementation,
            invoked=False,
            sandbox_id=sandbox.id,
            validated_return=verdict.get("result"),
        )
        _REGISTRY[tool.name] = tool
        _log(f"registered tool {tool.name!r} — {len(_REGISTRY)} tool(s) total")
        return tool
 
    except DaytonaError as e:
        # Surface, don't swallow — a bad sandbox call is not this lane's to hide.
        _log(f"DAYTONA ERROR — {type(e).__name__}: {e}")
        raise
 
    finally:
        if sandbox is not None:
            try:
                daytona.delete(sandbox)
                _log(f"sandbox {sandbox.id} deleted")
            except Exception as e:
                _log(f"cleanup failed (non-fatal, sandbox is ephemeral anyway): {e}")
 
 
def registered_tools() -> list[Tool]:
    """What the dashboard reads: name, signature, call_when, invoked-yet."""
    return list(_REGISTRY.values())
 
 
def reset() -> None:
    """Testing/demo helper only — NOT part of the pinned contract."""
    _log("reset() — clearing tool registry")
    _REGISTRY.clear()
 
 
if __name__ == "__main__":
    # Standalone sanity check — run this BEFORE touching harness.py.
    # Needs real DAYTONA_API_KEY in the environment; this will hit the network.
    print("=== standalone test, no harness ===")
    art = CodeArtifact(
        name="tests_pass",
        signature="tests_pass() -> bool",
        implementation="def tests_pass():\n    return True\n",
        call_when="before claiming a task is complete",
    )
    tool = materialize(art)
    print("tool registered:", tool)
    print("registered_tools():", registered_tools())