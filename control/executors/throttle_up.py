"""Executor for THROTTLE_UP commands: push remaining engines to compensate."""
from control.executors.base import Executor
from core.ksp_link import KSPLink


class ThrottleUpExecutor(Executor):
    command_type = "THROTTLE_UP"

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        # target may carry a throttle level (0-1); default to full.
        try:
            level = float(command.get("target", "") or 1.0)
        except ValueError:
            level = 1.0
        level = max(0.0, min(1.0, level))
        ksp.set_throttle(level)
        return True, f"throttle set to {level:.2f} to compensate for lost thrust"
