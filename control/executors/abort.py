"""Executor for ABORT commands: trigger the vehicle abort sequence."""
from control.executors.base import Executor
from core.ksp_link import KSPLink


class AbortExecutor(Executor):
    command_type = "ABORT"

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        ksp.abort()
        return True, "abort sequence triggered"
