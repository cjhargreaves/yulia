"""Executor for ENGINE_OUT commands — the full flight-controller response.

PROP just flags ENGINE_OUT with the failed engine. This executor decides and
performs the real response, using live telemetry + flight-dynamics math:
  1. shut down the diametrically OPPOSITE engine (restore thrust symmetry)
  2. safe the failed engine
  3. compute margins (TWR, delta-v, orbit reachability)
  4. if it can still make orbit -> throttle up to compensate
     else -> ABORT
"""
from control.executors.base import Executor
from core.ksp_link import KSPLink
from core import flight_dynamics as fd
from telemetry.stream_to_foundry import propulsion_records, vehicle_record


class EngineOutExecutor(Executor):
    command_type = "ENGINE_OUT"

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        failed = command.get("target", "")
        if not failed:
            return False, "no failed engine_id"
        # defend against PROP cramming multiple ids into one target
        failed = failed.split(",")[0].strip()

        steps = []

        # 1. shut the opposite engine for balance
        opp = ksp.opposite_engine_id(failed)
        if opp and ksp.shutdown_engine(opp):
            steps.append(f"shut opposite {opp}")
        else:
            steps.append("no opposite engine to balance")

        # 2. safe the failed engine
        ksp.shutdown_engine(failed)
        steps.append(f"safed {failed}")

        # 3. hold attitude — losing an engine pushes the vehicle off-axis, so
        # engage SAS to actively stabilize.
        ksp.set_sas(True)
        steps.append("SAS engaged to hold attitude")

        # 4. compute margins from live telemetry
        engines = propulsion_records(ksp.vessel)
        veh = vehicle_record(ksp.vessel)
        m = fd.assess(engines, veh, failed)

        # 5. decide: recover or abort.
        # Recoverable only if we can BOTH keep climbing AND still reach orbit.
        recoverable = m["can_climb_after_loss"] and m["reaches_orbit"]
        if recoverable:
            ksp.set_throttle(1.0)
            steps.append(
                f"throttle up (TWR {m['twr_after_loss']}, dv {m['remaining_dv_ms']}m/s, "
                f"reaches_orbit={m['reaches_orbit']})")
        else:
            ksp.abort()
            reason = ("cannot climb" if not m["can_climb_after_loss"]
                      else "cannot reach orbit")
            steps.append(
                f"ABORT — {reason} (TWR {m['twr_after_loss']}, "
                f"dv {m['remaining_dv_ms']}m/s, reaches_orbit={m['reaches_orbit']})")

        return True, "; ".join(steps)
