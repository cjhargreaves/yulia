"""Flight-dynamics math: real performance margins from telemetry.

Deterministic physics, not LLM guesswork. The FLIGHT agent reads these numbers
to decide a response; it does not compute them itself. All inputs come straight
from the telemetry we already stream.
"""
import math

G0 = 9.80665           # standard gravity, m/s^2 (for the rocket equation)
KERBIN_G = 9.81        # surface gravity used for weight/TWR
ORBIT_ALTITUDE_M = 70_000  # Kerbin: space / minimum stable orbit boundary


def twr(total_thrust_kn: float, mass_kg: float, g: float = KERBIN_G) -> float:
    """Thrust-to-weight ratio. < 1 means the vehicle cannot climb."""
    weight = mass_kg * g
    return (total_thrust_kn * 1000.0) / weight if weight else 0.0


def twr_after_loss(engines: list[dict], failed_id: str, mass_kg: float) -> float:
    """TWR with the failed engine's thrust removed."""
    remaining = sum(
        e.get("thrust_kn", 0.0) for e in engines if e.get("engine_id") != failed_id
    )
    return twr(remaining, mass_kg)


def remaining_dv(mass_kg: float, dry_mass_kg: float, specific_impulse_s: float) -> float:
    """Remaining delta-v via the Tsiolkovsky rocket equation (m/s).

    dv = Isp * g0 * ln(m_wet / m_dry)
    """
    if dry_mass_kg <= 0 or mass_kg <= dry_mass_kg or specific_impulse_s <= 0:
        return 0.0
    return specific_impulse_s * G0 * math.log(mass_kg / dry_mass_kg)


def reaches_orbit(apoapsis_m: float, vertical_speed: float, remaining_dv_ms: float,
                  dv_to_orbit_ms: float = 3400.0) -> bool:
    """Rough go/no-go: will we still make orbit?

    True if apoapsis is already at/above the orbit boundary, or we still hold
    more delta-v than a typical ascent-to-orbit budget requires. dv_to_orbit is
    a Kerbin-ascent rule of thumb (~3400 m/s).
    """
    if apoapsis_m >= ORBIT_ALTITUDE_M and vertical_speed >= 0:
        return True
    return remaining_dv_ms >= dv_to_orbit_ms


def assess(engines: list[dict], vehicle: dict, failed_id: str | None) -> dict:
    """Bundle the decision-grade margins for the FLIGHT agent.

    engines: list of per-engine telemetry dicts (Engine objects)
    vehicle: vehicle telemetry dict (Vehicle object)
    failed_id: engine_id that PROP flagged as out, or None
    """
    mass = vehicle.get("mass_kg", 0.0)
    dry = vehicle.get("dry_mass_kg", 0.0)
    # use the largest active Isp as representative for the current burn
    isp = max((e.get("specific_impulse", 0.0) for e in engines if e.get("active")),
              default=0.0)

    total_thrust = sum(e.get("thrust_kn", 0.0) for e in engines)
    twr_now = twr(total_thrust, mass)
    twr_loss = twr_after_loss(engines, failed_id, mass) if failed_id else twr_now
    dv = remaining_dv(mass, dry, isp)
    orbit_ok = reaches_orbit(vehicle.get("apoapsis_m", 0.0),
                             vehicle.get("vertical_speed", 0.0), dv)

    return {
        "twr_now": round(twr_now, 3),
        "twr_after_loss": round(twr_loss, 3),
        "can_climb_after_loss": twr_loss >= 1.0,
        "remaining_dv_ms": round(dv, 1),
        "reaches_orbit": orbit_ok,
        "altitude_m": vehicle.get("altitude_m", 0.0),
        "dynamic_pressure": vehicle.get("dynamic_pressure", 0.0),
    }
