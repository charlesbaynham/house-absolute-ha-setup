# TRV radiators stay hot although HA has closed the valve

Status: **open**. Mitigations merged and live (PR #97). Sync gap confirmed for the living room; drift not ruled out elsewhere.
Last updated: 2026-11-08.

## Symptom
Radiators (Sonoff TRVZB, PID-driven via `packages/climate_*.yaml`) stay hot when the PID helper
(`input_number.<room>_trv_valve_position`) is 0. A manual TRV re-adaptation usually fixes it.

## Hypotheses, in current order of suspicion
1. **Commanded position never reached the TRV (sync gap).** Owner's top suspicion as of 2026-11-08.
   The valve-sync blueprint (`blueprints/automation/arnie580/sonoff-trv-pid.yaml`) used to be
   edge-triggered on the helper only: no re-send after a dropped Zigbee write, a restart, or the TRV
   coming back online. A manual re-adaptation could also mask this, since it resets the device.
   - *Verified 2026-11-08:* `climate.trv_living_room` reported opening 100 / closing 0 (fully open)
     while `input_number.living_room_trv_valve_position` was 0 and the PID was off (smart mode off,
     parked position 0). Master bedroom and bedroom were consistent (opening 5 / closing 100).
   - *Plausible mechanism for the living room (not proven):* HA restarted 2026-11-07 ~17:19. The
     helper has `initial: 0`, so it resets to 0 on restart. The "apply smart mode" automation then
     writes the parked value (0), which is no change, so the sync automation never fires and the TRV
     keeps its old 100/0. The sync automation's `last_triggered` was 2026-11-07 15:30, before the
     restart.
   - *Fix in PR #97:* blueprint now re-applies on HA start, when the TRV entities leave
     unavailable/unknown, and every 10 min, writing only when the reported value is wrong.
2. **TRVZB calibration drift.** The motor loses its travel calibration, so "closed" is not
   closed. Evidence is community reports (VTherm discussions #831, #1369, #1896; Koenkk/zigbee-OTA
   #1062), not Sonoff statements. Reports tie it to many small valve moves (below ~3%) and to PID
   modes. The TRVZB (firmware up to 1.4.4) has **no Zigbee command to recalibrate**; only a manual
   re-adaptation works (remove a battery, refit, seat the head firmly, short-press the middle button
   so "Ad" runs). The Gen2 TRV-ZBT does have `valve_travel_calibration`.
   - Mitigation in PR #97: dead-band (`min_step`, default 3%) so PID wiggles don't move the valve,
     except to fully closed/open (so closing is always a full stroke).
3. **Config / control logic** (lower suspicion here):
   - `valve_closing_degree` < 100 means "closed" is partly open. Currently 100 when closed.
   - `smart_temperature_control` (TRV built-in) keeps the valve partly open until setpoint +2 °C. It
     is **off** on living room and bedroom, **on** for master bedroom (2026-11-08).
   - Master bedroom had `open_window` = on on 2026-11-08; switched off during recommissioning (see log).
4. **Mechanical** (adapter slip, pin under-reach, worn insert): only worth chasing if a fresh,
   correct adaptation still leaks. Sonoff publishes no stroke/force specs.

## How the valve is driven (as of PR #97)
Helper value `v` (0-100) → `closing = 100 - v`, `opening = min(v + 5, 100)` on the TRV's
`number.trv_<room>_valve_closing_degree` / `_opening_degree`. At `v = 0` that is closing 100 /
opening 5. Changes smaller than `min_step` are ignored unless `v` is 0 or 100.

Meaning of the two TRVZB settings (the `closing = 100 - v` / `opening = v + 5` mapping is inherited
from the upstream blueprint; the reason for the `+5` is **unverified**, probably to avoid an opening of 0):
- `valve_closing_degree`: how closed the valve is when the TRV decides to close. 100 = fully shut;
  0 = valve stays fully open even when it "closes".
- `valve_opening_degree`: cap on how far it opens when the TRV decides to heat.
- Consequence (untested): at `v = 0` the valve is not fully shut if the TRV's own thermostat logic asks
  for heat; it can crack open to 5%. Community reports suggest flow often only starts at 10-18%, so this
  is probably minor. If a radiator still runs warm at `v = 0`, test opening 0 (check the TRV accepts it).

## Watchdog
`blueprints/automation/charlesbaynham/trv-hot-while-closed-watchdog.yaml`, one instance per room
in `packages/climate_<room>.yaml`. Fires when helper < 1, TRV closing degree ≥ 99, and
(TRV local temperature − room sensor) > threshold for 1 h. Sends a persistent notification and a
push to `notify.mobile_app_pixel_6`.
- Threshold is **4 °C and untuned**. Idle TRV-minus-room offsets differed by room on 2026-10-31 /
  11-01: living room about -1.0, master bedroom about +1.4, bedroom about -2.8. Tune per room once
  real events are seen.
- Because the watchdog also fires in the sync-gap case, a notification does **not** by itself mean
  calibration drift. First check that the TRV's reported opening/closing degree matches the helper.

## How to tell the hypotheses apart
- Before touching anything on a hot-but-"closed" radiator: read `number.trv_<room>_valve_closing_degree`
  and `_opening_degree` live. Closing ≠ 100 with helper 0 means a sync problem (hypothesis 1).
  Closing = 100 and the radiator is still hot points to drift or mechanical (2 / 4).
- After PR #97 is live, a recurrence with closing = 100 is evidence for drift. A recurrence that
  self-heals within ~10 min is evidence the old gap was the cause.
- `sensor.trv_<room>_idle_steps` / `_closing_steps` were flat over the 8 days of history available
  on 2026-11-08 (living 234/296, master 58/279, bedroom 78/263). They look like adaptation-time
  values, not a live drift detector. A change in them would indicate a re-adaptation happened.

## Observation log
- **2026-11-08, master bedroom: TRV reinstalled and sensor batteries replaced (recommission).**
  Live checks: `climate.trv_master_bedroom` present; helper 0, closing 100, opening 5 (consistent,
  valve sync running). Changes made to match living room/bedroom: `smart_temperature_control` and
  `open_window` switched **off** (were on); setpoint sync automations (physical <-> PID) switched
  **on** (were off, last triggered 2025-11). **Blocker, not diagnosed:** `climate.master_bedroom_trv_pid_controller`
  does not exist live (living room and bedroom PID entities do). Smart mode / PID cannot run until it
  does. Cause unknown: HA error log is not exposed over REST; check Settings > System > Logs for
  `smart_thermostat` / `master_bedroom` errors, and the entity registry for a disabled entry.
  Sensor battery was replaced by the owner; its reported 0 % (last updated 11:51) is expected to be
  stale until the sensor next reports the battery attribute.
  - **Follow-up, 2026-11-08:** YAML `unique_id` and name changed to request a fresh registry entry,
    expected entity ID `climate.master_bedroom_trv_pid_controller_v2`. This has not yet been
    confirmed live; the old registry entry may remain separately.
- **2026-11-08, living room: sync gap confirmed as the cause of that radiator being hot.** Before the
  restart the TRV had closing 0 / opening 100 (fully open) while the helper was 0, and its local
  temperature sat at about 28.4-28.9 °C against 24.1 °C in the room. PR #97 was pulled and HA restarted
  at ~11:31. When the TRV came back online at 11:31:52, opening went 100 → 5 and closing was reported
  100, i.e. the blueprint corrected it with no manual action. The owner then pulled the batteries,
  reseated the head and re-ran adaptation at ~11:40; `idle_steps` changed 234 → 79 and `closing_steps`
  296 → 232 (so these do change on re-adaptation), and the owner manually cycled the helper 100 → 0 at
  11:42:33-36. So the first proper test was contaminated by the manual re-adaptation. **Not yet
  known:** whether the radiator now actually cools with the valve closed (TRV local temperature was
  still 28.6 °C at 11:42, only ~10 min after closing; a radiator takes tens of minutes to cool). Check
  `sensor.trv_living_room_local_temperature` falling towards the room temperature after ~1 h closed.
- **2026-11-08 12:44 UTC, living room, ~1 h after the re-adaptation:** valve settings stayed consistent
  with the helper (closing 100 / opening 5, helper 0; a Z2M/HA restart at 11:50:36-55 came back with the
  same values). TRV local temperature fell 28.6 (11:42) → 28.1 (11:52) → 27.6 (12:08) with no further
  report to 12:44 (the sensor only reports on ~0.5 °C changes), while the room sensor read 24.2-24.3.
  So it is cooling, not holding at a hot value, but it was still ~3.3 °C above room temperature (the
  idle baseline on 10-31/11-01 was about -1.0 °C below room), i.e. not yet cold. The watchdog had not
  fired (the difference dropped below its 4 °C threshold at ~11:52). **Verdict: encouraging, not
  conclusive.** A hand check of the radiator is the definitive test; the TRV head sensor is slow.
- Whether the living room would have been stuck anyway (the original cause of the dropped command) is
  unknown. The restart mechanism in hypothesis 1 is still a hypothesis.

## Data limits
- Recorder history on the live instance only went back to about 2026-10-31 when checked
  (queries beyond ~8 days returned empty), too little to calibrate thresholds.
- No radiator surface/pipe temperature sensor exists; "hot radiator" is inferred from the TRV's own
  local temperature.

## Ideas not built
- Automatic "closing 0 → 100" exercise when the watchdog fires. Community reports say it clears drift
  only sometimes, and it briefly heats the radiator.
- Log helper vs reported-device mismatches (to measure how often writes are lost).
- Replace with the Gen2 TRV-ZBT if on-demand recalibration is needed.

## Sources
Research report that started this (not in repo): "Sonoff TRVZB not closing fully: ranked fixes",
2026-11. Key external references: VTherm discussions #831 / #1369 / #1896 / issue #1790,
Koenkk/zigbee-OTA #1062, Koenkk/zigbee2mqtt #33489, Sonoff help page help.sonoff.tech/docs/trvzb.
