"""The single module that talks to the vehicle (kRPC).

Everything that reads from or commands Kerbal Space Program goes through here.
Swapping KSP for a real vehicle means reimplementing this one file against the
real comms link; nothing else in the system changes.
"""
import math

import krpc


class KSPLink:
    def __init__(self, name: str = "yulia-control"):
        self.conn = krpc.connect(name=name)
        self.vessel = self.conn.space_center.active_vessel

    # --- engine lookup -----------------------------------------------------

    def engine_by_id(self, engine_id: str):
        """Resolve an engine_id like 'Kerbal X-2' to its kRPC engine, or None.

        engine_id encodes vehicle name + engine index ('<vehicle>-<idx>'), which
        is how the telemetry bridge keys engines.
        """
        idx = self._index_of(engine_id)
        engines = self.vessel.parts.engines
        return engines[idx] if 0 <= idx < len(engines) else None

    @staticmethod
    def _index_of(engine_id: str) -> int:
        return int(engine_id.rsplit("-", 1)[1])

    def opposite_engine_id(self, engine_id: str) -> str | None:
        """Find the engine diametrically opposite the given one in the cluster.

        Uses each engine's radial position in the vessel reference frame (the
        plane perpendicular to the roll axis). The opposite engine is the one
        whose radial offset vector points most nearly the reverse direction.
        Returns its engine_id ('<vehicle>-<idx>'), or None if none is suitable.
        """
        engines = self.vessel.parts.engines
        idx = self._index_of(engine_id)
        if not (0 <= idx < len(engines)):
            return None

        rf = self.vessel.reference_frame
        # Vessel frame: x = right, y = forward (roll axis), z = up-ish; radial
        # offset is the (x, z) component, ignoring position along the roll axis.
        def radial(engine):
            x, _, z = engine.part.position(rf)
            return (x, z)

        fx, fz = radial(engines[idx])
        fmag = math.hypot(fx, fz)
        if fmag < 1e-3:
            return None  # the failed engine is on-axis; no meaningful "opposite"

        best, best_score = None, -2.0
        for i, e in enumerate(engines):
            if i == idx:
                continue
            ex, ez = radial(e)
            emag = math.hypot(ex, ez)
            if emag < 1e-3:
                continue
            # cosine of angle between the two radial vectors; -1 == opposite
            cos = (fx * ex + fz * ez) / (fmag * emag)
            score = -cos  # higher when more opposed
            if score > best_score:
                best, best_score = i, score

        if best is None:
            return None
        name = engine_id.rsplit("-", 1)[0]
        return f"{name}-{best}"

    # --- commands ----------------------------------------------------------

    def shutdown_engine(self, engine_id: str) -> bool:
        """Shut down a single engine. Returns True if the engine was found."""
        engine = self.engine_by_id(engine_id)
        if engine is None:
            return False
        engine.active = False
        return True

    def set_throttle(self, value: float) -> None:
        """Set vehicle throttle (0.0 - 1.0)."""
        self.vessel.control.throttle = max(0.0, min(1.0, value))

    def set_sas(self, on: bool = True) -> None:
        """Enable/disable SAS (stability assist) to hold attitude."""
        self.vessel.control.sas = on

    def set_rcs(self, on: bool = True) -> None:
        """Enable/disable RCS thrusters (fine attitude control)."""
        self.vessel.control.rcs = on

    def stage(self) -> None:
        """Activate the next stage (spacebar): decouple / jettison."""
        self.vessel.control.activate_next_stage()

    def abort(self) -> None:
        """Trigger the vehicle's abort action group."""
        self.vessel.control.abort = True
