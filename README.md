# Yulia

An aerospace operations platform built on an ontology-first philosophy and driven by
agentic AI. Real-world vehicle state is modeled as ontology objects; AI agents reason
over those objects, diagnose problems, and issue governed commands back to the vehicle.
Built on Palantir Foundry and AIP.

We simulated a full rocket launch in Kerbal Space Program and tapped its live flight
data through the kRPC interface, giving us a real-time telemetry stream that accurately
represents an actual rocket launch: thrust, propellant, engine health, attitude, and more,
updating every tick. The agents reason over that live data exactly as they would over a
real vehicle. Point the same pipeline at a real telemetry feed and nothing downstream
changes.

## The loop

```
Kerbal Space Program (kRPC)
  -> telemetry bridge        (telemetry/)
    -> Foundry streams        (propulsion_stream, vehicle_stream)
      -> Ontology objects      (Engine, Vehicle)
        -> AIP agents          (PROP reasons over the objects)
          -> Command object    (governed and audited: who, what, why)
            -> command bus      (control/) reads PENDING commands
              -> executor        -> kRPC -> vehicle responds
                -> telemetry reflects the result
```

## Layout

| Path | Purpose |
|---|---|
| `core/foundry.py` | Foundry client (host, token, ontology from `.env`) |
| `core/ksp_link.py` | The only module that talks to kRPC (vehicle I/O) |
| `telemetry/stream_to_foundry.py` | Kerbal Space Program to Foundry telemetry bridge |
| `control/command_bus.py` | Reads PENDING Commands, dispatches by type, marks done |
| `control/executors/` | One executor per command type (shutdown_engine, etc.) |
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

In Kerbal Space Program: vessel on the pad or flying, kRPC server started (green).

```bash
python scripts/run_telemetry.py     # stream telemetry to Foundry
python scripts/run_control.py       # run the command bus (executes commands in the vehicle)
```

## Foundry pieces (built in-platform)

- Objects: `Engine` (from propulsion_stream), `Vehicle` (from vehicle_stream), `Command` (writable)
- Agent: `PROP` in AIP Logic, returns a structured verdict (status, callout, failing_engine_id, reasoning)
- Actions: `create-command` (plus edit/delete), how agents issue governed commands

## Notes

- `.env` holds a live Foundry token and is gitignored. Never commit it.
- kRPC is isolated in `core/ksp_link.py`, so swapping Kerbal Space Program for a real vehicle is a one-file change.
