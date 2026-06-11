"""Entrypoint: run the command bus.

Reads PENDING commands from Foundry and executes them in the vehicle.
Run from the project root:  python scripts/run_control.py

Needs the kRPC server running (vehicle on the pad or flying).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from control.command_bus import run

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\ncommand bus stopped.")
