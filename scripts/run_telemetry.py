"""Entrypoint: stream KSP telemetry into Foundry.

Run from the project root:  python scripts/run_telemetry.py [--interval 1.0]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telemetry.stream_to_foundry import main

if __name__ == "__main__":
    main()
