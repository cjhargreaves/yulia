"""Publish a fake engine-out scenario to Foundry to test the autonomous chain.

No KSP needed. Streams 4 engines where one (Kerbal X-2) is collapsed while its
peers fire at 100%. This changes the Engine objects, which should fire the
Foundry Automation -> PROP -> create-command. Then we check if a command appeared.

  python test_engine_out.py          # publish the engine-out scenario once
  python test_engine_out.py --watch  # publish, then poll for a PROP command
"""
import argparse
import os
import time

from core.foundry import client

PROP_RID = os.environ["FOUNDRY_PROPULSION_STREAM_RID"]
VEH_RID = os.environ["FOUNDRY_VEHICLE_STREAM_RID"]
ONT = os.environ["FOUNDRY_ONTOLOGY"]
BRANCH = "master"


def engine(idx, thrust_pct, active=True, has_fuel=True, deprived=False):
    """Build one engine record. thrust_pct drives thrust_kn."""
    max_t = 178.6
    thrust = round(max_t * thrust_pct / 100, 2)
    return {
        "engine_id": f"Kerbal X-{idx}", "time": 20.0, "vehicle": "Kerbal X",
        "engine_idx": idx, "thrust_kn": thrust, "max_thrust_kn": max_t,
        "thrust_pct": float(thrust_pct), "throttle": 1.0, "thrust_limit": 1.0,
        "specific_impulse": 265.0, "vacuum_isp": 320.0, "has_fuel": has_fuel,
        "active": active, "can_restart": True, "is_deprived": deprived,
        "propellant_fill_pct": 0.0 if deprived else 50.0,
        "propellant_names": "LiquidFuel, Oxidizer", "gimbal_locked": False,
        "gimbal_range": 3.0, "temperature_k": 340.0, "max_temperature_k": 2000.0,
        "temperature_ratio": 0.17,
    }


def scenario():
    """3 engines firing at 100%, engine 2 collapsed (deprived, zero thrust)."""
    return [
        engine(1, 100.0),
        engine(2, 0.0, deprived=True, has_fuel=False),  # ENGINE-OUT
        engine(3, 100.0),
        engine(7, 100.0),
    ]


def cmd_count():
    objs = client.ontologies.OntologyObject.list(ontology=ONT, object_type="Command")
    d = objs[1] if isinstance(objs, tuple) else list(objs)
    rows = []
    for x in d:
        if isinstance(x, tuple) and x[0] == "data":
            rows.extend(x[1])
        else:
            rows.append(x)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="poll for a PROP command after publishing")
    args = ap.parse_args()

    before = len(cmd_count())
    recs = scenario()
    client.streams.Dataset.Stream.publish_records(
        dataset_rid=PROP_RID, stream_branch_name=BRANCH, records=recs)
    print(f"published engine-out scenario: {[ (r['engine_id'], r['thrust_pct']) for r in recs ]}")
    print(f"commands before: {before}")

    if not args.watch:
        print("run with --watch to poll for a PROP-issued command.")
        return

    print("watching for a PROP command (30s)...")
    for i in range(15):
        time.sleep(2)
        rows = cmd_count()
        if len(rows) > before:
            print(f"\nCOMMAND CREATED after {2*(i+1)}s:")
            for o in rows:
                print("  ", o.get("commandType"), "->", o.get("target"),
                      "| by", o.get("issuedBy"), "|", o.get("status"))
            return
        print(f"  ...{2*(i+1)}s, still {len(rows)} commands")
    print("\nno command appeared in 30s — automation may not be firing.")


if __name__ == "__main__":
    main()
