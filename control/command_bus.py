"""Command bus: the command center.

Polls Foundry for PENDING Command objects, dispatches each to the executor
registered for its command_type, runs it against the vehicle, and marks the
Command EXECUTED or FAILED (writing back the result for the audit trail).

Knows nothing about kRPC or any specific command. New command types plug in as
new executors in the registry below.
"""
import os
import time

from core.foundry import client
from core.ksp_link import KSPLink
from control.executors.shutdown_engine import ShutdownEngineExecutor
from control.executors.shutdown_opposite import ShutdownOppositeExecutor
from control.executors.throttle_up import ThrottleUpExecutor
from control.executors.abort import AbortExecutor

ONTOLOGY = os.environ["FOUNDRY_ONTOLOGY"]

# Register executors by command_type. Add new ones here.
EXECUTORS = {
    e.command_type: e
    for e in [
        ShutdownEngineExecutor(),
        ShutdownOppositeExecutor(),
        ThrottleUpExecutor(),
        AbortExecutor(),
    ]
}


def _unwrap(objs):
    rows = []
    for x in objs:
        if isinstance(x, tuple) and x and x[0] == "data":
            rows.extend(x[1])
        else:
            rows.append(x)
    return rows


def _props(o) -> dict:
    """Return an object's properties as a plain dict."""
    p = getattr(o, "properties", None)
    if isinstance(p, dict):
        return p
    if isinstance(o, dict):
        return o
    return dict(o)


def pending_commands() -> list[dict]:
    objs = client.ontologies.OntologyObject.list(ontology=ONTOLOGY, object_type="Command")
    rows = _unwrap(list(objs))
    cmds = [_props(o) for o in rows]
    return [c for c in cmds if c.get("status") == "PENDING"]


def mark(command: dict, status: str, detail: str) -> None:
    """Write the command's outcome back to Foundry via edit-command."""
    client.ontologies.Action.apply(
        ONTOLOGY,
        "edit-command",
        parameters={
            "Command": command["commandId"],
            "status": status,
            "reason": f"{command.get('reason', '')} | {detail}"[:1000],
            "commandType": command.get("commandType", ""),
            "target": command.get("target", ""),
            "issuedBy": command.get("issuedBy", ""),
            "created": command.get("created", ""),
        },
    )


def run(interval: float = 1.0) -> None:
    ksp = KSPLink()
    print(f"command bus online. executors: {list(EXECUTORS)}. Ctrl-C to stop.\n")
    while True:
        try:
            for cmd in pending_commands():
                ctype = cmd.get("commandType", "")
                executor = EXECUTORS.get(ctype)
                if executor is None:
                    print(f"  [skip] no executor for command_type={ctype}")
                    mark(cmd, "FAILED", f"no executor for {ctype}")
                    continue
                ok, detail = executor.execute(cmd, ksp)
                status = "EXECUTED" if ok else "FAILED"
                print(f"  [{status}] {ctype} target={cmd.get('target')} :: {detail}")
                mark(cmd, status, detail)
        except Exception as e:
            print(f"  [bus error: {type(e).__name__}: {e}]")
        time.sleep(interval)
