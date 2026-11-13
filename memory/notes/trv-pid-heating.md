---
name: trv-pid-heating
description: The per-room TRV PID heating pattern (packages/climate_{room}.yaml) — components, gains, valve arbitration, boost and smart modes (incl. the open smart-mode-off issue), adding a room, calibration drift, troubleshooting. Read before touching any room's heating; the off/setback/comfort policy is in heating-policy.
aliases: [TRV, PID, smart_thermostat, boost mode, smart mode, Sonoff TRVZB, radiator, parked valve]
updated: 2026-11-13
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

## Heating policy

The per-room off / setback / comfort policy (PR #106), its facts, by-hand rules and gotchas are in
[heating-policy](memory/notes/heating-policy.md). Do NOT write a PID's `hvac_mode` from another automation: the
policy reverts anything that is not a human.

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

## Smart mode off: valves are parked, the PID's demand is ignored

`[found: live, 2026-11-13]` Smart mode is now **on** in all three rooms (the booleans' `last_changed` is the 09:57 HA start; living room and bedroom valves followed the PID at 100 % while heating). The section below is the history of the off period.

`[found: live state + git history, 2026-11-12]` `input_boolean.smart_mode_{room}` was off in all three rooms
(since at least 2026-11-04). With it off the room-control blueprint holds the valve at the parked position
(0), so a room below setpoint with the PID in `heat` and `control_output` 100 still gets no hot water (master
bedroom 20.9 °C against 22, valve 0; bedroom the same). `[inferred]` Before #103 the smart-off thermostat ran
as a plain on/off controller whose output reached the valve, so the rooms heated by accident; #103 removed that
side effect. **Open, Charles to choose:** (1) turn smart mode on in the affected rooms (no code; the session
recommended it for the master bedroom), or (2) change `trv-room-control` so smart-off follows the thermostat
output (restores the old behaviour, makes the parked position meaningless). Not answered as of 2026-11-12.

## Adding a room

Copy an existing `packages/climate_{room}.yaml` and rename entities and blueprint inputs (the
control automation takes the valve-sync automation's entity id as an input, so keep its alias).
The copy already carries the policy helpers and automation (see [heating-policy](memory/notes/heating-policy.md)); there are no
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
