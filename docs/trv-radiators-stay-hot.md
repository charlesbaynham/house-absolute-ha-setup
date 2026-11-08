# TRV radiators stay hot although HA has closed the valve

Status: **open**. Mitigations merged/pending in PR #97. Cause not yet confirmed.
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
   - Master bedroom also had `open_window` = on on 2026-11-08, which is unexpected and unchecked.
4. **Mechanical** (adapter slip, pin under-reach, worn insert): only worth chasing if a fresh,
   correct adaptation still leaks. Sonoff publishes no stroke/force specs.

## How the valve is driven (as of PR #97)
Helper value `v` (0-100) → `closing = 100 - v`, `opening = min(v + 5, 100)` on the TRV's
`number.trv_<room>_valve_closing_degree` / `_opening_degree`. At `v = 0` that is closing 100 /
opening 5. Changes smaller than `min_step` are ignored unless `v` is 0 or 100.

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
