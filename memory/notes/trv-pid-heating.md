---
name: trv-pid-heating
description: The per-room TRV PID heating pattern (packages/climate_{room}.yaml) and the heating policy that decides off / setback / comfort per room (presence, back door, occupied, manual off) — components, gains, boost and smart modes, adding a room, calibration drift, troubleshooting. Read before touching any room's heating.
aliases: [TRV, PID, smart_thermostat, boost mode, smart mode, Sonoff TRVZB, radiator, heating policy, setback, away mode, occupied]
updated: 2026-11-12
---

# TRV PID controller pattern

Migrated from the old `CLAUDE.md` on 2026-11-08; `[found: CLAUDE.md, 2026-11-08]` throughout.
Reference implementation: `packages/climate_living_room.yaml` (collapsed onto the room-control blueprint on 2026-11-08). Implemented for living room, master
bedroom and bedroom (all with boost). Open investigation of radiators staying hot:
[docs/trv-radiators-stay-hot.md](docs/trv-radiators-stay-hot.md).

## One package per room — `packages/climate_{room_name}.yaml`

1. **Two input numbers**: `input_number.{room}_trv_pid_output` (0–100, the PID's heater) and
   `input_number.{room}_trv_valve_position` (0–100, what the valve-sync automation copies onto the
   TRV). The PID never writes the valve helper; only the room control automation does (see below).
2. **`smart_thermostat` climate entity** — `heater:` is the PID output helper, `target_sensor:`
   the room's external temperature sensor. Gains used in every room: `kp: 30`, `ki: 0.005`,
   `kd: 2000`, `pwm: 0`.
3. **Valve sync automation** — blueprint `arnie580/sonoff-trv-pid.yaml`; copies the helper onto the
   TRV's valve opening/closing degree numbers.
4. **External temperature sync** — blueprint
   `photomoose/sonoff-trvzb-external-temperature-sensor-calibration.yaml`; feeds the external
   sensor into the TRV.
5. **Room control automation** — blueprint `charlesbaynham/trv-room-control.yaml`, one automation
   per room (`<Room> TRV - control`, `mode: queued`). Branches by trigger id: *setpoint sync* (TRV
   → PID and PID → TRV, each gated by a "setpoints differ" check to avoid a loop), *boost on*,
   *boost timeout* and *smart mode*. All checks are made at run time, not as automation conditions.
   - **Boost** — helpers `input_boolean.boost_mode_{room}`, `input_datetime.boost_start_{room}`,
     template `button.boost_{room}`. On: stamp start, `smart_thermostat.set_pid_mode` `off`, valve to
     100%. Timeout polls every 5 min and ends boost once `boost_start` is over `boost_duration`
     (default 60 min) old. Boost end re-applies smart mode.
   - **Smart mode** — `input_boolean.smart_mode_{room}`. This is the blueprint's default branch: runs
     on smart-mode/parked-position change, boost end, HA start, or a **manual trigger**
     Turns the valve-sync automation on (it no longer sets the PID to `heat`: the heating policy owns
     off/heat, see below); smart on → `set_pid_mode: auto`; off → PID stopped and valve helper set to
     `input_number.{room}_trv_parked_valve_position`. Skipped during boost. The TRVs' Z2M "smart
     temperature control" switches are a different built-in feature and are hidden.
     `set_pid_mode` accepts only `auto`/`off`.

What stays per room (blueprints cannot create them): the helpers, the template button and the
`smart_thermostat` climate entity.

## Heating policy — off / setback / comfort (since 2026-11-10, PR #106)

`[found: repo + live, 2026-11-10]` One blueprint, `blueprints/automation/charlesbaynham/trv-room-policy.yaml`,
instantiated per room in `packages/climate_{room}.yaml`, decides each PID climate's `off`/`heat` and setpoint
from the current facts (level-triggered; nothing is remembered to undo later, so restarts and missed events
self-heal). It replaced the away-mode state machine, the back-door pause, the master-bedroom-follows-Charles
automation (#104) and the 4am automation. Rules, first match wins: room switched off → off; back door open →
off; room occupied (switch, or boost running) → comfort; room follows a person who is away → off (master
bedroom follows Charles); `house_far_away` → off; nobody home → setback (comfort − 2 °C); else comfort.

- Per room helpers: `{room}_comfort_setpoint` (the user's number; the PID setpoint is derived),
  `{room}_policy_last_setpoint` (echo guard), `{room}_occupied`, `{room}_heating_disabled`,
  `{room}_heating_status` (text: mode and why: look here first when asking "why is it off?").
- Facts, `packages/heating_presence.yaml`: `binary_sensor.house_far_away` (both Charles and Gaby >50 km
  AND nobody home, `delay_on` 30 min; after a restart the 30 min count from the restart),
  `binary_sensor.charles_away_for_heating` (trigger-based latch: on once `charles_confirmed_away` has held 10
  min, off only when `person.charles` is `home`, so a stale location never brings the heating back).
- By hand (a service call with a user context): turning the PID on against a presence rule sets `occupied`;
  turning it off sets `heating_disabled`; turning it on again clears it. An off room holds the comfort setpoint.
  `occupied` clears when the person the room follows gets home (or, for other rooms, when an empty house gets
  someone home). The back door beats everything.
- Do NOT write a PID's `hvac_mode` from another automation: the policy reverts anything that is not a human.
  Express the new rule as a fact or a switch the policy reads.
- Edits to the setpoint (physical TRV via the room-control mirror, or dashboard) become the comfort setpoint
  (+2 °C while in setback). Known limitation: a stale TRV setpoint after the TRV was unavailable during a
  presence change can inflate comfort by 2 °C (see docs/heating-control-state-machines.md).
- Gotchas learned: a `for:` state trigger never fires if the entity is already in the state at HA start;
  trigger-based template entities restore from extra stored data, not just state; on the very first start the
  Charles latch took `off` from an early `person` event, so the master bedroom heated for ~10 min that evening
  (self-corrected; first deployment only). Do not spoof `binary_sensor.anyone_home` live: it arms "Vacuum when
  everyone leaves" (20 h `last_triggered` guard) and "Turn off all lights when everyone leaves".
- Test heating/presence logic on the mock house first: `tests/ha_mock` (README there).

## Why the PID writes a separate output helper

`[found: live test, living room, 2026-11-08]` With `pid_mode: off` the smart_thermostat freezes its
output at the last value but its 60 s `keep_alive` tick keeps writing that frozen value to its
heater. When the heater was the valve helper itself, **boost (valve 100) and the parked position
(smart mode off) were overwritten within ≤60 s** (parked 10 → 22.4 after ~55 s; also visible in the
12:52 UTC history before the migration). Fixed on 2026-11-08: the PID now drives
`{room}_trv_pid_output`, and the room control blueprint is the only writer of the valve helper:
**0** if the PID climate is `off` (back door, far-away mode) → else **100** if boost → else the
**PID output** if smart mode is on → else the **parked position**. It re-evaluates on PID output
changes, PID climate off/on, smart mode, boost, parked position, HA start and manual trigger.
Verified in a real HA 2026.10 core (mocked PID, 23 checks incl. keep-alive rewrites during boost and
with a parked position) and live after merge, see the log.

## Adding a room

Copy an existing `packages/climate_{room}.yaml` and rename entities and blueprint inputs (the
control automation takes the valve-sync automation's entity id as an input, so keep its alias).
The copy already carries the policy helpers and automation (see "Heating policy"); there are no
hardcoded per-room lists elsewhere any more. Add the room's own mock-house scenarios if its rules differ.
Prerequisites: TRV paired in HA, an external temperature sensor available, TRV set to
external-sensor mode in Z2M, the Smart Thermostat (PID) HACS integration installed.

After the merge, give the room's user-facing helpers an area (standing rule in `WORKSPACE.md`): smart mode, boost,
occupied, switched off, comfort setpoint, heating status, parked valve position and valve position. The PID output,
last-written setpoint and boost start helpers stay area-less (internal).

## Calibration drift

The TRVZB motor can lose its travel calibration (radiator hot with the valve "closed"). There is
no Zigbee command to recalibrate; the cure is a manual re-adaptation (remove a battery, refit, seat
the head firmly, short-press the middle button). Mitigations in the repo: the valve sync blueprint
re-asserts the commanded position every 10 min and on start, ignores PID changes under 3% (except
fully closed/open), and
`blueprints/automation/charlesbaynham/trv-hot-while-closed-watchdog.yaml` notifies when the TRV
temperature stays above room temperature while the valve is commanded closed (per-room threshold,
untuned).

## Troubleshooting

- Not responding → is the valve sync automation running? Valve wrong → the room control automation is the only writer of the valve helper; read its arbitration order above.
- Inaccurate temperature → is the external sensor sync active?
- Fail-safe mode → the external sensor must report at least every 2 hours.
- Setpoints not syncing, boost or smart mode not applying → is the `<Room> TRV - control` automation enabled?
- Setpoint loop → check the "setpoints differ" template condition first.
