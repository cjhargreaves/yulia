# Yulia

Autonomous mission control for aerospace operations. A swarm of AI flight-controller
agents monitors live vehicle telemetry, diagnoses anomalies, and issues governed
commands back to the vehicle — built on Palantir Foundry + AIP.

Telemetry today comes from Kerbal Space Program (via kRPC) as a stand-in for a real
vehicle; the architecture is source-agnostic — swap the telemetry source and the
ontology, agents, and command loop are unchanged.

## The loop

```
KSP (kRPC)
  → telemetry bridge        (telemetry/)
    → Foundry streams        (propulsion_stream, vehicle_stream)
      → Ontology objects      (Engine, Vehicle)
        → AIP agents          (PROP — reasons over the objects)
          → Command object    (governed, audited: who/what/why)
            → command bus      (control/) reads PENDING commands
              → executor        → kRPC → vehicle responds
                → telemetry reflects the result
```

## Layout

| Path | Purpose |
|---|---|
| `core/foundry.py` | Foundry client (host/token/ontology from `.env`) |
| `core/ksp_link.py` | The only module that talks to kRPC (vehicle I/O) |
| `telemetry/stream_to_foundry.py` | KSP → Foundry telemetry bridge |
| `control/command_bus.py` | Reads PENDING Commands, dispatches by type, marks done |
| `control/executors/` | One executor per command type (shutdown_engine, ...) |
| `agents/prop_reference.py` | Reference/fallback PROP (the live PROP runs in AIP Logic) |
| `scripts/` | Entrypoints (`run_telemetry.py`, `run_control.py`) |

## Setup

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# create .env (gitignored) with FOUNDRY_HOST, FOUNDRY_TOKEN, FOUNDRY_ONTOLOGY,
# and the stream / object-type RIDs.
```

## Run

In KSP: vessel on the pad/flying, kRPC server started (green).

```bash
python scripts/run_telemetry.py     # stream telemetry → Foundry
python scripts/run_control.py       # run the command bus (executes commands in KSP)
```

## Foundry pieces (built in-platform)

- **Objects:** `Engine` (← propulsion_stream), `Vehicle` (← vehicle_stream), `Command` (writable)
- **Agent:** `PROP` in AIP Logic — structured verdict (status / callout / failing_engine_id / reasoning)
- **Actions:** `create-command` (+ edit/delete) — how agents issue governed commands

## Notes

- `.env` holds a live Foundry token and is gitignored — never commit it.
- kRPC is isolated in `core/ksp_link.py`; swapping KSP for a real vehicle is a one-file change.
