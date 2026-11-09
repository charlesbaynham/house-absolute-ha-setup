# Heating control: the parallel "state machines" (2026-11-09)

Why this note exists: a restart-reset bug was found in the away-mode state machine, and it is one
symptom of heating being controlled by several independent writers with no shared model.
Verified facts are dated and say how they were checked; everything under "Proposal" is a design
suggestion, not a decision.

## Verified: away mode is stuck after a restart (live, 2026-11-09 09:21Z, read-only API)

- 08:44:13Z the state machine ran home -> away; `input_select.climate_away_mode_state` = `away`,
  living room / master bedroom / bedroom setpoints reduced by 2 (21->19, 22->20, 19->17) and
  `away_mode_*_original_temp` held 21 / 22 / 19.
- 08:47:23Z HA restarted. Afterwards: state `home` (last_changed 08:47:23), all three originals
  `19.0` (last_changed 08:47:23), setpoints still 19 / 20 / 17, `binary_sensor.anyone_home` off.
  `automation.climate_state_machine` last_triggered is still 08:44:13: it did not run after the restart.
- Cause (config, `packages/climate_away_mode.yaml`): `initial: home` on the input_select and
  `initial: 19` on the three input_numbers. A helper with `initial` ignores its restored value on
  every start. The automation has no start trigger and triggers only on `anyone_home` /
  far-away changes.
- Consequence (inferred from the YAML, not exercised): when someone gets home, `desired_state`
  (`home`) equals `current_state` (`home`), the "only act if the state changes" condition stops
  the run, and the setpoints are never restored. Even if it did run, it would restore 19 for every
  room because the originals were reset. Rooms stay 2 degC low until someone sets them by hand.
- Trigger frequency: every HA restart while the state is `away` or `far_away`, including restarts
  the Git pull add-on does after merges.

## The writers that act on `climate.<room>_trv_pid_controller`

| Writer | Acts on | Remembers "what I changed" in |
|---|---|---|
| `climate_away_mode.yaml` state machine | setpoint -2 / restore; `turn_off` / `turn_on` all rooms | input_select + 3 input_numbers (reset on restart, see above) |
| `back_door.yaml` | `turn_off` all rooms, `heat` the ones that were heating | input_boolean + input_text list |
| `climate_master_bedroom_away.yaml` (PR #104) | master bedroom off / heat | input_boolean flag + override |
| `trv-room-control` blueprint | `heat` on re-apply, TRV<->PID setpoint mirror, valve arbitration | none (level-triggered) |
| `climate_master_bedroom.yaml` 4am restart | `heat`, setpoint 22 (disabled, last ran 2025-11-19) | self-disables |
| Humans (dashboard, physical TRV) | anything | nothing |

Each writer keeps its own private memory of what it changed, and none of them knows about the
others. Presence is defined four different ways: `anyone_home` (away mode),
`both_charles_and_gaby_far_away` (>50 km for 30 min), `charles_confirmed_away` (>10 km, fresh report;
alarm and PR #104) and `person.charles != home` (door alert).

## Interactions found by reading the code (inferred, not all exercised)

1. Restart reset above.
2. The setpoint is both the user's intent and the controller's output. Away mode overwrites it
   and restores a copy; a change made by hand while away is lost on return.
3. far_away -> away/home runs `climate.turn_on` on all rooms. That overrides a room the back door
   is holding off, and a room PR #104 switched off (PR #104 re-offs it within seconds; the back
   door does not re-pause).
4. The back-door resume list is captured at open. If far-away mode switches rooms off while the
   door is open, closing the door turns them back on.
5. home -> far_away directly (unlikely but possible) never stores the original setpoints.
6. Adding a room means editing hardcoded lists in `back_door.yaml`, `climate_away_mode.yaml` and
   now `climate_master_bedroom_away.yaml`.
7. Dead things: `automation.climate_turn_off_pid_controllers_when_both_far_away` and
   `automation.climate_turn_on_pid_controllers_when_someone_returns` (both `unavailable` in the
   registry), and the self-disabled 4am automation.

## Proposal (not decided): one level-triggered policy per room

Replace "react to transitions and remember what I did" with "compute what the room should be
doing now, and make it so".

- **Facts** (one definition each, already mostly present): `anyone_home`,
  `both_far_away`, `charles_confirmed_away`, back door contact.
- **Per-room user intent** (helpers, no `initial`): `<room>_comfort_setpoint`,
  `<room>_occupied_override`. The physical TRV / dashboard edit the comfort setpoint, never an
  offset-adjusted copy.
- **One policy blueprint, one instance per room.** Priority, first match wins:
  back door open -> `off`; room override -> `comfort`; room follows a person who is confirmed away
  -> `off` (master bedroom: Charles); both far away -> `off`; nobody home -> `setback` (-2);
  else `comfort`. It publishes the result and the reason as a template sensor
  (`sensor.<room>_heating_policy`, attribute `reason`) and applies it: `hvac_mode` and PID
  setpoint = comfort - offset. Triggered by any input changing, HA start and a periodic
  reconcile, so a missed event or a restart self-heals.
- **Stays as is:** `trv-room-control` (valve arbitration, boost, setpoint mirror to the TRV),
  because it is already the sole valve writer and level-triggered.
- **Removed:** the away-mode state machine and its four helpers, the heating half of
  `back_door.yaml` (the alert stays), `climate_master_bedroom_away.yaml` (becomes the room's
  "follows Charles" input), the 4am automation, the two orphaned registry entries.
- **Gains:** no stored "originals", restart-safe, no ordering races between writers, "why is it
  off?" answered by one attribute, adding a room is one instance.
- **Open questions for Charles:** is -2 setback still the wanted behaviour; should the bedroom
  follow Gaby the way the master bedroom follows Charles; should the back door beat an
  "occupied" override.
- **Migration:** one room first (master bedroom, where the person-follow behaviour is new), verify
  live with the spoof method in `memory/log.md` (2026-11-09 LEARNED), then the other two rooms,
  then delete the old machinery.

## Immediate fix, independent of the proposal (not yet made)

Remove `initial:` from `climate_away_mode_state` and the three originals, and add a
`homeassistant: start` trigger to the state machine. One-off live repair needed first, because
the restore store currently holds the wrong values: set the state to `away` and the originals to
21 / 22 / 19 (setpoints untouched). Superseded entirely if the proposal goes ahead.
