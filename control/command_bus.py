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
from control.executors.engine_out import EngineOutExecutor

ONTOLOGY = os.environ["FOUNDRY_ONTOLOGY"]

# Register executors by command_type. Add new ones here.
EXECUTORS = {
    e.command_type: e
    for e in [
        EngineOutExecutor(),        # full response: balance + compensate / abort
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


# Human-in-the-loop: the bus executes a command ONLY after an operator approves
# it on the dashboard (status -> APPROVED). PROP-created commands sit PENDING and
# do nothing until accepted. (To run fully autonomous instead, add "PENDING".)
EXECUTABLE_STATUSES = {"APPROVED"}


def pending_commands() -> list[dict]:
    objs = client.ontologies.OntologyObject.list(ontology=ONTOLOGY, object_type="Command")
    rows = _unwrap(list(objs))
    cmds = [_props(o) for o in rows]
    return [c for c in cmds if c.get("status") in EXECUTABLE_STATUSES]


def _all_commands() -> list[dict]:
    objs = client.ontologies.OntologyObject.list(ontology=ONTOLOGY, object_type="Command")
    return [_props(o) for o in _unwrap(list(objs))]


def dedupe_commands() -> int:
    """Keep one open command per (commandType, target); drop redundant ones.

    PROP can fire repeatedly while an engine stays degraded, spamming the feed.
    We delete an open (PENDING) command if EITHER:
      - another open command already exists for the same engine+type, OR
      - that engine+type has already been handled (an EXECUTED command exists).
    We never delete EXECUTED/APPROVED/REJECTED commands. Returns count removed.
    """
    open_states = {"PENDING", None, ""}
    cmds = _all_commands()

    # engine+type pairs already handled (executed) — don't re-flag these
    handled = {
        (c.get("commandType"), c.get("target"))
        for c in cmds if c.get("status") == "EXECUTED"
    }

    seen = set()
    removed = 0
    for c in cmds:
        if c.get("status") not in open_states:
            continue
        key = (c.get("commandType"), c.get("target"))
        if key in seen or key in handled:
            cid = c.get("commandId")
            if cid:
                try:
                    client.ontologies.Action.apply(
                        ONTOLOGY, "delete-command", parameters={"Command": cid})
                    removed += 1
                except Exception:
                    pass
        else:
            seen.add(key)
    return removed


def mark(command: dict, status: str, detail: str) -> None:
    """Write the command's outcome back to Foundry via edit-command.

    Stamps the real execution time (the LLM/PROP can't know wall-clock time, so
    we set the true timestamp here when the command is actually handled).
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
            "created": now_iso,
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
