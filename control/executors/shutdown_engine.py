"""Executor for SHUTDOWN_ENGINE commands."""
from control.executors.base import Executor
from core.ksp_link import KSPLink


class ShutdownEngineExecutor(Executor):
    command_type = "SHUTDOWN_ENGINE"

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        target = command.get("target", "")
        if not target:
            return False, "no target engine_id"
        ok = ksp.shutdown_engine(target)
        if ok:
            return True, f"engine {target} commanded inactive"
        return False, f"engine {target} not found on vehicle"
