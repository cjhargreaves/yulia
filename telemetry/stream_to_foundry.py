"""Live bridge: KSP telemetry -> Foundry streams.

Reads telemetry from kRPC each tick and publishes to two Foundry streaming
datasets:
  - propulsion_stream : one record per engine (stable key vehicle-engine_idx)
  - vehicle_stream    : one record for the vehicle (flight dynamics + guidance)

Run with a vessel on the pad/flying and the kRPC server started.

  python stream_to_foundry.py            # publish every 1s
  python stream_to_foundry.py --interval 0.5
"""
import argparse
import os
import time

import krpc

from core.foundry import client

PROPULSION_RID = os.environ["FOUNDRY_PROPULSION_STREAM_RID"]
VEHICLE_RID = os.environ["FOUNDRY_VEHICLE_STREAM_RID"]
BRANCH = "master"

# Fallback name when KSP hands us an unresolved localization token (e.g.
# "#autoLOC_501232") instead of a real vessel name. Override with VEHICLE_NAME.
DEFAULT_VEHICLE_NAME = os.environ.get("VEHICLE_NAME", "Kerbal X")


def vehicle_name(vessel) -> str:
    """Clean vehicle name; never let a KSP localization token through."""
    raw = vessel.name
    if not raw or raw.startswith("#autoLOC"):
        return DEFAULT_VEHICLE_NAME
    return raw


def _propellant_fill_pct(engine) -> float:
    """Average fill % across this engine's propellants (0-100)."""
    fills = []
    for p in engine.propellants:
        cap = p.total_resource_capacity
        if cap:
            fills.append(100 * p.total_resource_available / cap)
    return round(sum(fills) / len(fills), 1) if fills else 0.0


def propulsion_records(vessel) -> list[dict]:
    """One record per engine."""
    met = round(vessel.met, 1)
    name = vehicle_name(vessel)
    recs = []
    for i, e in enumerate(vessel.parts.engines):
        p = e.part
        max_t = e.max_thrust
        temp, max_temp = p.temperature, p.max_temperature
        recs.append({
            "engine_id": f"{name}-{i}",            # stable: updates over time
            "time": met,
            "vehicle": name,
            "engine_idx": i,
            "thrust_kn": round(e.thrust / 1000, 2),
            "max_thrust_kn": round(max_t / 1000, 2),
            "thrust_pct": round(100 * e.thrust / max_t, 1) if max_t else 0.0,
            "throttle": round(e.throttle, 3),
            "thrust_limit": round(e.thrust_limit, 3),
            "specific_impulse": round(e.specific_impulse, 1),
            "vacuum_isp": round(e.vacuum_specific_impulse, 1),
            "has_fuel": e.has_fuel,
            "active": e.active,
            "can_restart": e.can_restart,
            "is_deprived": any(p_.is_deprived for p_ in e.propellants),
            "propellant_fill_pct": _propellant_fill_pct(e),
            "propellant_names": ", ".join(e.propellant_names),
            "gimbal_locked": e.gimbal_locked,
            "gimbal_range": round(e.gimbal_range, 2),
            "temperature_k": round(temp, 1),
            "max_temperature_k": round(max_temp, 1),
            "temperature_ratio": round(temp / max_temp, 3) if max_temp else 0.0,
        })
    return recs


def vehicle_record(vessel) -> dict:
    """One record for the vehicle: flight dynamics + guidance/control."""
    f = vessel.flight(vessel.orbit.body.reference_frame)
    orbit = vessel.orbit
    mass = vessel.mass
    thrust = vessel.thrust
    # TWR = thrust / weight; weight ~ mass * surface gravity (9.81 on Kerbin SL)
    twr = round(thrust / (mass * 9.81), 2) if mass else 0.0
    return {
        "vehicle": vehicle_name(vessel),
        "time": round(vessel.met, 1),
        "situation": str(vessel.situation),
        "stage": vessel.control.current_stage,
        # flight dynamics
        "altitude_m": round(f.mean_altitude, 1),
        "surface_altitude_m": round(f.surface_altitude, 1),
        "vertical_speed": round(f.vertical_speed, 2),
        "horizontal_speed": round(f.horizontal_speed, 2),
        "speed": round(f.speed, 2),
        "mach": round(f.mach, 3),
        "dynamic_pressure": round(f.dynamic_pressure, 1),
        "g_force": round(f.g_force, 2),
        "mass_kg": round(mass, 1),
        "dry_mass_kg": round(vessel.dry_mass, 1),
        "thrust_to_weight": twr,
        "total_thrust_kn": round(thrust / 1000, 2),
        "available_thrust_kn": round(vessel.available_thrust / 1000, 2),
        # guidance / control
        "pitch": round(f.pitch, 2),
        "heading": round(f.heading, 2),
        "roll": round(f.roll, 2),
        "angle_of_attack": round(f.angle_of_attack, 2),
        "apoapsis_m": round(orbit.apoapsis_altitude, 1),
        "periapsis_m": round(orbit.periapsis_altitude, 1),
        "time_to_apoapsis": round(orbit.time_to_apoapsis, 1),
        "latitude": round(f.latitude, 5),
        "longitude": round(f.longitude, 5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between publishes")
    args = ap.parse_args()

    conn = krpc.connect(name="stream")
    vessel = conn.space_center.active_vessel
    print(f"streaming {vehicle_name(vessel)} -> Foundry (propulsion + vehicle). Ctrl-C to stop.\n")

    while True:
        try:
            props = propulsion_records(vessel)
            veh = vehicle_record(vessel)
            client.streams.Dataset.Stream.publish_records(
                dataset_rid=PROPULSION_RID, stream_branch_name=BRANCH, records=props)
            client.streams.Dataset.Stream.publish_record(
                dataset_rid=VEHICLE_RID, stream_branch_name=BRANCH, record=veh)
            print(f"t+{veh['time']:.0f}s  {len(props)} engines | "
                  f"alt={veh['altitude_m']:.0f}m TWR={veh['thrust_to_weight']} "
                  f"thrust={[r['thrust_kn'] for r in props]}")
        except Exception as e:
            print(f"[error: {type(e).__name__}: {e}]")
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstream stopped.")
