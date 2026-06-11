"""Executor interface.

An executor handles one command_type. To add a new vehicle response (throttle
down, abort, vent, etc.), write a new Executor subclass and register it with the
command bus. The bus needs no changes.
"""
from core.ksp_link import KSPLink


class Executor:
    #: the command_type string this executor handles, e.g. "SHUTDOWN_ENGINE"
    command_type: str = ""

    def execute(self, command: dict, ksp: KSPLink) -> tuple[bool, str]:
        """Carry out the command against the vehicle.

        Returns (ok, detail): ok=True if executed, plus a short detail string
        for the audit log / command status.
        """
        raise NotImplementedError
