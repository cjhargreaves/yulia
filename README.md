# Yulia

An aerospace operations platform built on an ontology-first philosophy and driven by
agentic AI. Real-world vehicle state is modeled as ontology objects; AI agents reason
over those objects, diagnose problems, and issue governed commands back to the vehicle.

I simulated a full rocket launch in Kerbal Space Program and tapped its live flight
data through the kRPC interface, giving us a real-time telemetry stream that accurately
represents an actual rocket launch: thrust, propellant, engine health, attitude, and more,
updating every tick. The agents reason over that live data exactly as they would over a
real vehicle. Point the same pipeline at a real telemetry feed and nothing downstream
changes.

## Design philosophy

The system separates three concerns on purpose:

- **Detection and reasoning (the agent).** PROP, an AIP Logic agent modeled on a
  propulsion flight controller, watches the engine objects and diagnoses anomalies by
  comparing each engine against its peers.
- **Decision math (deterministic).** Orbital and performance margins are computed in
  code, not guessed by a language model. The agent reasons; the physics is exact.
- **Governance (human in the loop).** The agent issues a governed Command with a
  recommended action plan. Nothing reaches the vehicle until a human approves it on the
  dashboard, and every decision is logged and auditable.

Everything is ontology-first: real vehicle state is modeled in Foundry as objects
(Engine, Vehicle, Command), and every layer reasons over those objects, never raw streams.

## The loop

```
Kerbal Space Program (kRPC)
  -> telemetry bridge        (yulia.py / telemetry/)
    -> Foundry streams        (propulsion_stream, vehicle_stream)
      -> Ontology objects      (Engine, Vehicle)
        -> Foundry Automation fires the PROP agent (AIP Logic) on telemetry change
          -> PROP detects an engine-out, creates a governed Command (ENGINE_OUT)
             with a recommended action plan, status PENDING
            -> operator reviews the command + plan on the dashboard and APPROVES
              -> command bus      (control/) executes only APPROVED commands
                -> executor computes the response with flight-dynamics math:
                   shut the opposite engine (balance), engage SAS to hold attitude,
                   then throttle up to compensate, or ABORT if orbit is unreachable
                  -> kRPC -> vehicle responds -> telemetry reflects the result
```

The reasoning lives in Foundry/AIP. `yulia.py` is the bridge: it streams telemetry up
and executes the commands a human has approved. Orbital and performance margins are
computed deterministically in Python (`core/flight_dynamics.py`).

## Dashboard

A Foundry Workshop dashboard sits on top of the ontology as the human-in-the-loop view.
It shows the live telemetry, PROP's verdicts as they happen, and the Command log. The
PROP automation can run in two modes:

- Automatic: PROP's commands execute immediately (hands-off operation).
- Staged for review: each command waits on the dashboard for a human to approve or reject
  before it executes.

Same pipeline, same audit trail; the dashboard is where an operator watches the agents
work and stays in control of what reaches the vehicle.

## Layout

| Path | Purpose |
|---|---|
| `yulia.py` | Single entry point: streams telemetry and executes commands |
| `core/foundry.py` | Foundry client (host, token, ontology from `.env`) |
| `core/ksp_link.py` | The only module that talks to kRPC (shutdown, throttle, abort, opposite-engine geometry) |
| `core/flight_dynamics.py` | Performance margins: TWR, delta-v (rocket equation), orbit reachability |
| `telemetry/stream_to_foundry.py` | Builds telemetry records for the two Foundry streams |
| `control/command_bus.py` | Reads PENDING Commands, dispatches by type to executors, marks done |
| `control/executors/` | One executor per command type (engine_out, shutdown_engine, shutdown_opposite, throttle_up, abort) |
| `agents/prop_reference.py` | Reference PROP (the live PROP runs in AIP Logic) |
| `send_command.py` | Manually issue a command (testing) |

## Setup

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# create .env (gitignored) with FOUNDRY_HOST, FOUNDRY_TOKEN, FOUNDRY_ONTOLOGY,
# the stream RIDs, and the object-type RIDs.
```

## Run

In Kerbal Space Program: vessel on the pad or flying, kRPC server started (green).

```bash
python yulia.py                # the whole loop: telemetry up, approved commands executed
```

## Foundry pieces (built in-platform)

- Objects: `Engine` (from propulsion_stream), `Vehicle` (from vehicle_stream), `Command` (writable, audited)
- Agent: `PROP` in AIP Logic, returns a structured verdict (status, callout, failing_engine_id, reasoning) and, on a genuine engine-out, issues an `ENGINE_OUT` command
- Automation: fires PROP automatically when Engine telemetry changes
- Actions: `create-command` / `edit-command` / `delete-command`

## The flight-dynamics math

When PROP flags an engine-out, the executor computes performance margins from the live
telemetry and acts on them. This lives in `core/flight_dynamics.py`.

### Thrust-to-weight ratio (TWR)

Whether the vehicle can still climb after losing an engine. Sum the thrust of the
remaining (non-failed) engines and divide by the vehicle's weight:

$$
\text{TWR} = \frac{F_{\text{remaining}}}{m \cdot g}
= \frac{\sum_{i \neq \text{failed}} F_i}{m \cdot g}
$$

where $F_i$ is each engine's current thrust (N), $m$ is vehicle mass (kg), and
$g = 9.81\ \text{m/s}^2$ (Kerbin surface gravity). If $\text{TWR} < 1$, weight exceeds
thrust and the vehicle cannot climb, which is an immediate abort condition.

### Remaining delta-v (Tsiolkovsky rocket equation)

How much velocity change the vehicle still has left, the best single measure of whether it
can finish the climb to orbit:

$$
\Delta v = I_{sp} \cdot g_0 \cdot \ln\!\left(\frac{m_{\text{wet}}}{m_{\text{dry}}}\right)
$$

where $I_{sp}$ is the engine's specific impulse (s), $g_0 = 9.80665\ \text{m/s}^2$ (the
standard gravity used to convert $I_{sp}$ to a velocity), $m_{\text{wet}}$ is current total
mass, and $m_{\text{dry}}$ is mass with propellant spent. The ratio
$m_{\text{wet}} / m_{\text{dry}}$ is the mass fraction; its natural log gives the usable
$\Delta v$.

### Orbit reachability (the go / no-go)

The vehicle is judged able to reach orbit if either condition holds:

$$
\left(h_{ap} \geq h_{orbit} \;\wedge\; v_{\uparrow} \geq 0\right)
\quad \lor \quad
\Delta v \geq \Delta v_{orbit}
$$

- $h_{ap}$ is apoapsis altitude, $h_{orbit} = 70000\ \text{m}$ (Kerbin's space boundary),
  $v_{\uparrow}$ is vertical speed. If apoapsis is already at or above the boundary and the
  vehicle is still rising, the trajectory is coasting to orbit.
- Otherwise it must still hold more delta-v than a typical Kerbin ascent budget,
  $\Delta v_{orbit} \approx 3400\ \text{m/s}$.

### The decision

The executor recovers the vehicle only if it can both keep climbing and still reach orbit:

$$
\text{recoverable} = \left(\text{TWR}_{\text{after loss}} \geq 1\right)
\;\wedge\;
\text{reachesOrbit}
$$

- Recoverable: shut the diametrically opposite engine to restore thrust symmetry, then
  throttle up to compensate for the lost thrust.
- Not recoverable: ABORT (cannot climb, or cannot reach orbit).

The agent detects and classifies; the physics computes the margins; the response follows
from the numbers.

## Adding capability

- New vehicle response: add an executor in `control/executors/` and register it in `command_bus.py`.
- New agent: add it in AIP Logic and, optionally, an automation that fires it.

## Notes

- `.env` holds a live Foundry token and is gitignored. Never commit it.
- kRPC is isolated in `core/ksp_link.py`, so swapping Kerbal Space Program for a real vehicle is a one-file change.
