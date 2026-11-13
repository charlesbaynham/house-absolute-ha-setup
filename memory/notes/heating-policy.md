---
name: heating-policy
description: The heating policy blueprint that decides off / setback / comfort per room from presence, back door, occupied and switched-off switches (PR #106) — rules, helpers, by-hand behaviour, gotchas, open follow-ups. Read when asking why a room's heating is on or off, or adding a presence rule.
aliases: [heating policy, setback, away mode, occupied, presence heating, far away, back door, trv-room-policy]
updated: 2026-11-13
---

# Heating policy — off / setback / comfort (since 2026-11-10, PR #106)

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
- **Live observation 2026-11-13 (train trip, people leaving London)** `[found: live API monitor]`: Charles and
  Gaby left; `anyone_home` off 18:29:03; rooms went to setback; `charles_away_for_heating` on 19:53:00 (10 min
  after `person.charles` became `not_home` 19:42) and the master bedroom went off at once; both people >50 km
  at 20:15:44; `house_far_away` on 20:46:03 (+30 min), living room and bedroom PIDs off in the same second,
  valve helpers 0, status "off - house far away". Held across the 10-minute reconciles for 30+ minutes.
  Not verifiable from HA: whether the valves are physically shut. The bedroom TRV kept reporting
  `hvac_action: heating` (its own sensor 21.6 < target 25) after the valve helper went to 0.
- **Setback was a no-op that day (the stale-echo bug, new trigger)** `[found: history + logbook, 2026-11-13]`:
  at 18:29:52 `anyone_home` flickered on for 0.2 s and off again. The policy wrote comfort (24) then setback
  (22) to the PID; the physical TRV echoed the 24 0.8 s late, the mirror wrote that onto the PID at 18:29:53.593,
  and the policy (in setback, last-written 22) read it as a hand edit: comfort became 26 (and 25, 24 in the
  other rooms). Setback then held 24 / 23, i.e. the user's original comfort, so nothing was saved until
  far-away, and after return the rooms will target 2 °C above what was set. `[inferred]` Any presence flicker
  (on then off within about a second) can do this, not just a TRV outage. Not fixed; comfort helpers are
  `input_number.{room}_comfort_setpoint` (original values: living room 24, bedroom 23, master bedroom 22).
- Test heating/presence logic on the mock house first: `tests/ha_mock` (README there). Valve behaviour and the open smart-mode-off issue are in [trv-pid-heating](memory/notes/trv-pid-heating.md).

## Open follow-ups (context, not an agenda)

- Two heating orphans remain in the registry: `automation.climate_turn_off_pid_controllers_when_both_far_away`
  and `automation.climate_turn_on_pid_controllers_when_someone_returns`; whether to remove them is Charles's
  call (`ha_live.py orphans --remove`). About 41 unrelated orphans exist and are untouched. `[found: live, 2026-11-10]`
- The latch's "adopt at start" branch in `charles_away_for_heating` is misleading (never ran on the first
  deployment); removing it is an optional follow-up. `[found: live, 2026-11-10]`
- `button.boost_master_bedroom` was absent from the live state list on 2026-11-09 although its `boost_mode`
  boolean existed; not investigated. `[found: live, 2026-11-09]`
- Bedroom and master bedroom control paths (PR #103 fix) were only exercised on the living room live. `[found: live test, 2026-11-08]`
- Lighting is deliberately independent of `occupied` and of the heating policy: lights use only motion sensors,
  so they work when people other than Gaby and Charles are home `[stated]` (Charles, 2026-11-10). Separate
  open point: `automations.yaml` "Turn off all lights when everyone leaves" fires once, 5 min after
  `anyone_home` goes off; Charles may want it removed or restricted. `[found: repo, 2026-11-10]`
