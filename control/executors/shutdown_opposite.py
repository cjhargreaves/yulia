"""Executor for SHUTDOWN_OPPOSITE commands.

Given the failed engine (target), shut down the diametrically opposite engine to
restore thrust symmetry and stop the vehicle yawing/rolling. This is the
non-obvious flight-controller response to an asymmetric engine-out.
"""
from control.executors.base import Executor
from core.ksp_link import KSPLink


class ShutdownOppositeExecutor(Executor):
    command_type = "SHUTDOWN_OPPOSITE"

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        failed = command.get("target", "")
        if not failed:
            return False, "no failed engine_id provided"
        opposite = ksp.opposite_engine_id(failed)
        if opposite is None:
            return False, f"no opposite engine found for {failed} (on-axis or single engine)"
        ok = ksp.shutdown_engine(opposite)
        if ok:
            return True, f"shut down {opposite} (opposite {failed}) to restore thrust symmetry"
        return False, f"opposite engine {opposite} not found"
