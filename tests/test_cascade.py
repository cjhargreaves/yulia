"""Verify the ENGINE_OUT response cascade actually runs, with fake telemetry.

No KSP, no Foundry. A fake vehicle records every command the executor issues, so
we can confirm the full flight-controller response fires correctly in both the
recoverable case (shut opposite + throttle up) and the unrecoverable case (abort).

  python tests/test_cascade.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import telemetry.stream_to_foundry as bridge
from control.executors.engine_out import EngineOutExecutor


class FakeKSP:
    """Stand-in for KSPLink that records actions instead of touching a game."""
    def __init__(self, engine_ids):
        self.engine_ids = engine_ids
        self.actions = []
        self.vessel = object()  # placeholder; telemetry funcs are stubbed below

    def opposite_engine_id(self, failed):
        # simple model: opposite of "X-2" is "X-0" etc. just return a known peer
        others = [e for e in self.engine_ids if e != failed]
        return others[0] if others else None

    def shutdown_engine(self, engine_id):
        self.actions.append(("shutdown_engine", engine_id))
        return engine_id in self.engine_ids

    def set_throttle(self, value):
        self.actions.append(("set_throttle", value))

    def abort(self):
        self.actions.append(("abort", None))


def fake_engines(failed_id, vehicle="Kerbal X"):
    """4 engines: one out, peers firing."""
    def e(idx, pct, dep=False):
        mt = 178.6
        return {"engine_id": f"{vehicle}-{idx}", "thrust_kn": round(mt*pct/100, 1),
                "max_thrust_kn": mt, "thrust_pct": float(pct), "active": True,
                "has_fuel": not dep, "is_deprived": dep, "specific_impulse": 265.0}
    out_idx = int(failed_id.rsplit("-", 1)[1])
    rows = []
    for idx in [0, 1, 2, 3]:
        rows.append(e(idx, 0.0, dep=True) if idx == out_idx else e(idx, 100.0))
    return rows


def run_scenario(name, failed_id, vehicle_state):
    print(f"\n=== {name} ===")
    engines = [f"Kerbal X-{i}" for i in range(4)]
    ksp = FakeKSP(engines)

    # stub the telemetry readers the executor calls
    bridge.propulsion_records = lambda v: fake_engines(failed_id)
    bridge.vehicle_record = lambda v: vehicle_state
    # the executor imports these names directly, so patch there too
    import control.executors.engine_out as eo
    eo.propulsion_records = lambda v: fake_engines(failed_id)
    eo.vehicle_record = lambda v: vehicle_state

    ok, detail = EngineOutExecutor().execute({"target": failed_id}, ksp)
    print(f"failed engine: {failed_id}")
    print("actions performed:")
    for a in ksp.actions:
        print("   ", a)
    print("result:", detail)


if __name__ == "__main__":
    # Recoverable: already coasting to orbit (apoapsis above 70km boundary) ->
    # throttle up and press on.
    run_scenario(
        "RECOVERABLE engine-out (expect: shut opposite + throttle up)",
        "Kerbal X-2",
        {"mass_kg": 40000, "dry_mass_kg": 12000, "apoapsis_m": 80000,
         "vertical_speed": 50, "dynamic_pressure": 200},
    )

    # Unrecoverable: low and heavy, almost no propellant margin -> abort
    run_scenario(
        "UNRECOVERABLE engine-out (expect: abort)",
        "Kerbal X-2",
        {"mass_kg": 40000, "dry_mass_kg": 39000, "apoapsis_m": 2000,
         "vertical_speed": 5, "dynamic_pressure": 9000},
    )
