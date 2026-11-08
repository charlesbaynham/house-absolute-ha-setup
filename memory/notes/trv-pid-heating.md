---
name: trv-pid-heating
description: The per-room TRV PID heating pattern (packages/climate_{room}.yaml) — components, gains, boost and smart modes, adding a room, calibration drift, troubleshooting. Read before touching any room's heating.
aliases: [TRV, PID, smart_thermostat, boost mode, smart mode, Sonoff TRVZB, radiator]
updated: 2026-11-08
---

# TRV PID controller pattern

Migrated from the old `CLAUDE.md` on 2026-11-08; `[found: CLAUDE.md, 2026-11-08]` throughout.
Reference implementation: `packages/climate_living_room.yaml` (collapsed onto the room-control blueprint on 2026-11-08). Implemented for living room, master
bedroom and bedroom (all with boost). Open investigation of radiators staying hot:
[docs/trv-radiators-stay-hot.md](docs/trv-radiators-stay-hot.md).

## One package per room — `packages/climate_{room_name}.yaml`

1. **Input Number** `input_number.{room}_trv_valve_position` — 0–100 valve position the PID drives.
2. **`smart_thermostat` climate entity** — `heater:` is the input_number above, `target_sensor:`
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
     (`back_door.yaml` uses that). Turns the valve-sync automation on, sets the PID to `heat`; smart
     on → `set_pid_mode: auto`; off → PID stopped and valve helper set to
     `input_number.{room}_trv_parked_valve_position`. Skipped during boost. The TRVs' Z2M "smart
     temperature control" switches are a different built-in feature and are hidden.
     `set_pid_mode` accepts only `auto`/`off`.

What stays per room (blueprints cannot create them): the helpers, the template button and the
`smart_thermostat` climate entity.

## Adding a room

Copy an existing `packages/climate_{room}.yaml` and rename entities and blueprint inputs (the
control automation takes the valve-sync automation's entity id as an input, so keep its alias).
Also add the room to the hardcoded per-room lists in `back_door.yaml` and `climate_away_mode.yaml`.
Prerequisites: TRV paired in HA, an external temperature sensor available, TRV set to
external-sensor mode in Z2M, the Smart Thermostat (PID) HACS integration installed.

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

- Not responding → is the valve sync automation running?
- Inaccurate temperature → is the external sensor sync active?
- Fail-safe mode → the external sensor must report at least every 2 hours.
- Setpoints not syncing, boost or smart mode not applying → is the `<Room> TRV - control` automation enabled?
- Setpoint loop → check the "setpoints differ" template condition first.
