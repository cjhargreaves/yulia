"""Yulia — single entry point. Run this one thing; it runs everything.

One background process that, every tick:
  1. streams live vehicle telemetry from Kerbal Space Program into Foundry
  2. executes any PENDING Commands back in the vehicle via kRPC

The reasoning happens entirely in Foundry: a Foundry Automation runs the PROP
agent (AIP Logic) automatically when Engine telemetry changes, and PROP issues
the governed Commands. yulia is only the bridge between the vehicle and Foundry.

    python yulia.py                 # run it
    python yulia.py --interval 1.0  # seconds per tick
"""
import argparse
import os
import time

from core.foundry import client
from core.ksp_link import KSPLink
from telemetry.stream_to_foundry import (
    PROPULSION_RID, VEHICLE_RID, BRANCH,
    propulsion_records, vehicle_record,
)
from control.command_bus import pending_commands, mark, EXECUTORS

ONTOLOGY = os.environ["FOUNDRY_ONTOLOGY"]


def stream_telemetry(vessel):
    props = propulsion_records(vessel)
    veh = vehicle_record(vessel)
    client.streams.Dataset.Stream.publish_records(
        dataset_rid=PROPULSION_RID, stream_branch_name=BRANCH, records=props)
    client.streams.Dataset.Stream.publish_record(
        dataset_rid=VEHICLE_RID, stream_branch_name=BRANCH, record=veh)
    return veh, props


def execute_commands(ksp):
    for cmd in pending_commands():
        ctype = cmd.get("commandType", "")
        executor = EXECUTORS.get(ctype)
        if executor is None:
            mark(cmd, "FAILED", f"no executor for {ctype}")
            print(f"  [skip] no executor for {ctype}")
            continue
        ok, detail = executor.execute(cmd, ksp)
        status = "EXECUTED" if ok else "FAILED"
        mark(cmd, status, detail)
        print(f"  [{status}] {ctype} target={cmd.get('target')} :: {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=1.0, help="seconds per tick")
    args = ap.parse_args()

    ksp = KSPLink(name="yulia")
    print(f"Yulia online — {ksp.vessel.name}. telemetry + PROP + control. Ctrl-C to stop.\n")

    while True:
        try:
            veh, props = stream_telemetry(ksp.vessel)
            execute_commands(ksp)
            print(f"t+{veh['time']:.0f}s  {len(props)} engines  "
                  f"alt={veh['altitude_m']:.0f}m  TWR={veh['thrust_to_weight']}")
        except Exception as e:
            print(f"  [tick error: {type(e).__name__}: {e}]")
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nYulia stopped.")
