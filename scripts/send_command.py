"""Manually issue a command to the vehicle (for testing the command bus).

Creates a PENDING Command in Foundry; the running command bus picks it up and
executes it in the vehicle.

Examples:
  python scripts/send_command.py SHUTDOWN_ENGINE "Kerbal X-2"
  python scripts/send_command.py SHUTDOWN_ENGINE "Kerbal X-2" --reason "manual test"
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.foundry import client

ONTOLOGY = os.environ["FOUNDRY_ONTOLOGY"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command_type", help="e.g. SHUTDOWN_ENGINE")
    ap.add_argument("target", help="e.g. 'Kerbal X-2' (engine_id) or vehicle name")
    ap.add_argument("--reason", default="manual test command")
    ap.add_argument("--issued-by", default="TEST")
    args = ap.parse_args()

    res = client.ontologies.Action.apply(
        ONTOLOGY,
        "create-command",
        parameters={
            "commandType": args.command_type,
            "target": args.target,
            "reason": args.reason,
            "issuedBy": args.issued_by,
            "status": "PENDING",
            "created": "now",
        },
    )
    ok = getattr(getattr(res, "validation", None), "result", "?")
    print(f"issued {args.command_type} -> {args.target}  (validation: {ok})")


if __name__ == "__main__":
    main()
