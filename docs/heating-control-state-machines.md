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

## Implementation (branch `heating-policy`, tested on the mock house, 2026-11-09)

The proposal above is implemented as `blueprints/automation/charlesbaynham/trv-room-policy.yaml`
(one instance per room), `packages/heating_presence.yaml` (the facts) and extra helpers in the three
`packages/climate_<room>.yaml`. Removed: `climate_away_mode.yaml` (state machine, input_select,
stored originals), `climate_master_bedroom_away.yaml`, the heating half of `back_door.yaml`, the 4am
automation, and the forced `heat` at start in `trv-room-control.yaml`.

Decisions that went beyond the proposal (flag if you disagree):

1. **`occupied` overrides every presence rule** (person-follow, far away, setback), per room, for all
   three rooms, not just the master bedroom. It clears itself when the person the room follows gets
   home. The back door still wins.
2. **Boost counts as occupied while it runs** (60 min), then the room returns to the policy. Previously
   boost during far-away/back-door had no effect (PID off).
3. **A manual off is a switch.** Because the policy owns off/heat it would otherwise undo a deliberate
   off: turning a room off by hand sets `<room>_heating_disabled`; turning it on by hand clears it.
4. **Edits to the setpoint (TRV or dashboard) set the comfort setpoint**, plus the 2 degC offset while
   nobody is home. Comfort is never overwritten by the machinery.
5. **After a restart the far-away 30 minutes count from the restart**: `binary_sensor.house_far_away` is a
   plain template sensor with `delay_on: 30 min` that also requires nobody home. Until it is on the rooms sit
   in setback, not off. (Harry home alone with Charles and Gaby far away is a normal house: heating on.)
6. **An off room holds the comfort setpoint** (not a stale setback value), so a later edit is never guessed.

Verified on the mock (real HA 2026.10, this repo's YAML, the real smart_thermostat; 62 scenarios):
presence rules and debounces, overrides, back door (including open through far-away), a restart in
every state (comfort/setpoints/latches/statuses identical afterwards), the world changing while HA was
down, no flicker of an off room at restart, TRV-edit semantics, no redundant writes on the reconcile
tick, flapping, the valve helper, and migration from today's live state. Ten deliberate mutations of
the blueprint and latches were all caught by the suite.

Not verifiable on the mock: real `person`/device tracker behaviour, real Zigbee timing, the physical TRV.
Hence the post-merge live test.

## Changes after an independent review (2026-11-10)

A separate reviewer found, and the mock confirmed: (1) Harry home alone while Charles and Gaby were far away
got no heating (the far-away rule ignored `anyone_home`; the old machine checked it first); (2) an edit made
while an off room's PID held a reduced value, or made by a stale TRV echo, inflated comfort by the offset;
(3) `occupied` never cleared in rooms that follow nobody; (4) the by-hand "on" needed two presses when the
room was both switched off and person-away; (5) the policy ran on every sensor report. Fixed in this PR, each
with a regression test. Also simplified: the far-away latch became a state-based sensor, the 30 s start
delay and the unreachable "seed by hand" path were removed.

## Known limitations (not fixed here)

- **A stale TRV echo can still inflate comfort.** If the physical TRV is unavailable (Z2M/broker restart)
  while everyone leaves, it comes back still holding the old setpoint; the existing mirror writes that onto
  the PID, and during setback the policy reads it as someone turning the dial, so comfort becomes old + 2.
  Rare, mild (2 degC warmer until someone sets it), but silent. The real cure is to stop writing the setback
  into the setpoint the TRV displays (a bigger redesign); a cheap mitigation is to ignore an "edit" that
  arrives while the TRV has just left `unavailable`.
- An unavailable back door sensor counts as closed (the old pause flag held the last state).
- Deploying while everyone is already far away: nothing runs until the first 10 minute reconcile, the rooms
  stay as they were, then sit in setback until the 30 minutes pass.

## Deployment notes

- The comfort helpers are new, so the first run reconstructs them from the PID setpoints (plus 2 degC only
  while the room is in setback). With someone home nothing moves: comfort equals the current setpoints. If
  nobody is home at that moment, check all three comfort values afterwards (an off room reads its setpoint
  as comfort).
- Old entities become unavailable in the registry and need removing: `input_select.climate_away_mode_state`,
  `input_number.away_mode_*_original_temp`, `input_boolean.back_door_heating_paused`,
  `input_text.back_door_heating_resume`, `input_boolean.master_bedroom_heating_away_override` and
  `..._off_for_away`, and the automations `climate_state_machine`, `back_door_pause_heating_while_open`,
  `master_bedroom_heating_off_while_charles_is_away`, `master_bedroom_restart_heating_at_4am`.
