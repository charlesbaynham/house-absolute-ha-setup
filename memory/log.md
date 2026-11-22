# Memory log (append-only)

<!--
Every session APPENDS terse observations here as it works — never edit or
reorder existing lines. The memory-compact skill's filing pass files them into
memory/notes/ and the digest, then removes exactly the lines it filed. Git
history preserves everything.

Format, one observation per line:

- [YYYY-MM-DD] TYPE: observation

TYPE is one of:
  DECISION  — a choice was made (record the choice AND the reason)
  STATE     — something changed: built, fixed, broke, merged, deployed
  LEARNED   — a fact worth not re-discovering (gotcha, quirk, preference)
  OPEN      — a question raised or task deferred
  RESOURCE  — an ID, path, URL, or environment fact worth keeping
  CORRECTION— something previously believed/recorded is wrong

Rules for writers:
- One line each, written at the moment the thing happens — not batched at the end
  (sessions die without warning; unlogged observations are lost).
- Provenance matters: "User decided X" vs "I suggested X (not yet confirmed)".
  Never log your own suggestion as the user's decision.
- Never log secrets, tokens, or credentials.
- Hypotheticals stay marked as hypothetical.
-->

<!-- compaction-baseline: filed 2026-11-13T01:25:30Z -->
- [2026-11-13] STATE: replaced the `ha-api-token` skill with `fetching-secrets` (ported from ha-workspace, trimmed of lab-only content, HA-token recipe kept); WORKSPACE.md, digest and ha-sync-and-deploy updated. `ha-test-harness` keeps its own ephemeral-key flow (`live_keygen.sh`/`ha_live.py`) — not merged.
- [2026-11-13] DECISION: Charles asked for ha-workspace's secret-handling auto-mode soft_deny rules in automode.json (plaintext-in-tool-result, Secret Server gate bypass), trimmed of lab-host specifics. Rules load only via agent-tools/automode/install.sh at environment setup; `automode-check` reports drift until the environment is re-installed.
- [2026-11-13] STATE: Charles reported "unknown action smart_thermostat.set_pid_mode" repairs on the "<Room> TRV - apply smart mode" automations. [found: live API, 2026-11-13] False alarm: the service is registered live; those automations were removed when the room control blueprint absorbed them (2026-11-08), and their 3 repair issues (created 2026-11-08T15:18Z, a restart before smart_thermostat had registered its services) were never cleared. Cleared via the repairs fix flow (POST /api/repairs/issues/fix + /fix/<flow_id>, same as the UI Submit button). Orphaned `automation.*_unknown_action`/`service_not_found` repairs after an automation is removed from YAML are not auto-deleted.
- [2026-11-13] GOTCHA: `$S/repairs.py`-style check of live repair issues needs a websocket (`repairs/list_issues`); only aiohttp in a scratch venv works here (system python has none). Live repair issues left: PVE/PBS backup notifications `notify.mobile_app_pixel_6` (since 2026-09-24, not ours to clear unasked).
- [2026-11-13] STATE: live test of away heating (Charles and Gaby on a train out of London, Charles asked for a read-only watch): setback 18:29, master bedroom off 19:53 (Charles latch), `house_far_away` on 20:46:03 and living room + bedroom off, stable across reconciles. No changes made. Details in memory/notes/heating-policy.md.
- [2026-11-13] GOTCHA: setback did nothing today: an `anyone_home` on/off flicker at 18:29:52 plus a late TRV echo made the policy read it as a hand edit and raise comfort by 2 (26/25/24 vs 24/23/22). Open: Charles to decide on a fix (ignore echoes within seconds of the policy's own write, or debounce `anyone_home`); comfort helpers need resetting by hand.
- [2026-11-13] STATE: smart mode is on in all three rooms (digest said off); digest corrected.
- [2026-11-14] DECISION: Charles proposed a 10 s dead time as the fix for the flicker/echo comfort inflation; implemented as blueprint input `echo_dead_time` (default 10) gating only the edit-adoption step, keyed on `last_written` helper's `last_changed`: PR #108. After merge: reset the comfort helpers by hand (24/23/22 living/bed/master), then check live without spoofing anyone_home.
- [2026-11-14] GOTCHA: `setup_mock.sh --ha-version 2026.11.1` gives a venv where pytest cannot start (uv resolves pytest-homeassistant-custom-component 0.2.1); use 2026.10.0 (plugin 0.13.371). Noted in the ha-test-harness SKILL.md (in PR #108).
- [2026-11-14] STATE: PR #108 merged 14:45Z and live after the restart (HA up 14:47Z, heating held off through it). Live test on the living room (rooms off, nobody home, snapshot restored exactly): stale TRV/PID value inside the dead time reverted in 20 ms with comfort unchanged; edit after the dead time adopted. Open: comfort helpers still 26/25/24, offered to reset to 24/23/22 (Charles to say). house_far_away was on immediately after the restart (restored), not 30 min later.
- [2026-11-15] STATE: comfort helpers reset live at Charles's request: bedroom 25->23, master bedroom 24->22 (living room already 24, set by Charles at 10:06Z). Rooms off (house far away), PID/TRV setpoints followed, valves 0. The 2026-11-13 inflation is fully undone.
- [2026-11-16] LEARNED: master bedroom TRV sensor fell 22 -> 19.1 at 12:00 UTC; no HA cause (logbook, entity histories, config all checked); 19.1 is the cold-radiator baseline. It had been warm with valve helper 0 because the TRV's own thermostat cracks the valve to its 5 % opening degree whenever local < setpoint - 0.4 (PID off does not stop it), plus leak-by with a nightly rhythm shared with the living room. Details in docs/trv-radiators-stay-hot.md.
- [2026-11-16] OPEN: what cut the hot supply to the master bedroom radiator at ~12:00 (outside HA: boiler programmer / zone valve / manual valve?). Charles to say whether anything changed physically.
- [2026-11-16] DECISION: Charles asked to cut the TRV opening offset from +5 to +1 (valve-sync blueprint sonoff-trv-pid.yaml, all three rooms) so the TRV's own thermostat can barely open the valve while the PID is off; PR #109. After merge: check valve_opening_degree reads 1 at helper 0 in each room.
- [2026-11-16] STATE: PR #109 merged 22:49Z and live: the sync re-asserted at 22:51:25Z and all three TRVs now report opening 1 / closing 100 at helper 0 (was 5/100). No restart needed for a blueprint change. Open: watch whether the master bedroom TRV still flips to heating and whether the radiator warms.
- [2026-11-21] DECISION: Charles asked the heating to stay off 1 h after the living room door closes, with an input boolean to cancel. Built as `input_boolean.back_door_heating_hold` + `timer.back_door_heating_hold` (restore) + automation in packages/back_door.yaml; blueprint rule 2 reads the boolean like an open door. "Living room door" taken to be `binary_sensor.backdoor_sensor_contact` (the only door sensor besides the front door) [inferred].
- [2026-11-21] STATE: hold built and tested on the mock house (tests/ha_mock/test_policy_back_door_hold.py, 80 pass; 4 new mutations caught); PR open, not merged. Existing door tests now end the hold via `close_door_and_end_hold`.
- [2026-11-21] OPEN: after merge, assign `input_boolean.back_door_heating_hold` to an area (WORKSPACE.md rule), then test it live (door is not spoofable; use the boolean/timer and check status text of a room, restoring after).
- [2026-11-22] STATE: researched heating schedules (Charles: temporary manual edits revert at the next schedule change, schedule edits permanent, weekday/weekend split, prefer an existing plugin). Candidates [found: web, 2026-11-22]: HACS Scheduler (nielsfaber; component v3.3.9 1 Nov 2026 in HACS default, card is a custom repo; fires only at slot start, so manual edits hold until the next slot; one `weekdays` set per schedule so weekday/weekend = two schedules; any service, so `input_number.set_value` on the comfort helper); built-in `schedule` helper (per-day blocks with `data` attributes, needs an automation to apply); Velair (young, climate.* only, "until next block" option) and kneave Climate Scheduler (climate.* only, override behaviour unverified).
- [2026-11-22] GOTCHA: a scheduler must write `input_number.{room}_comfort_setpoint`, NOT the PID climate: during setback the policy reads a PID setpoint edit as comfort + offset, so climate-targeting schedulers (Velair, kneave, scheduler on the climate) would inflate comfort by 2 °C. [inferred from trv-room-policy.yaml]
- [2026-11-22] OPEN: not yet decided or built. Unverified: whether the scheduler card's UI can target an input_number; that Scheduler re-fires the active slot on HA start (so a Git-pull restart discards a manual override); whether Scheduler/HACS/Workday are installed live (no token this session).
- [2026-11-22] DECISION (proposed, not yet confirmed by Charles): Charles wants only a graphical editor from third parties and will wire the rest with automations, or write his own editor. Findings [found: web + HA core source, 2026-11-22]: core `schedule` helper (UI-created, `editable: true`) already has a graphical editor with per-block `data` (primitives only) shown as attributes while the block is active; `schedule.block_started` fires at back-to-back boundaries too, `block_ended` only on off; WS `schedule/list|create|update|delete` (create/update/delete admin-only, `name` required, update replaces whole day lists); YAML schedules not editable. Scheduler component has no event/trigger API for automations. yybd Schedule Helper Card (HACS default, v2.5.1) edits the core helper but its value is per schedule and it writes its own automations. Own paint-grid card (~300 lines JS in www/, testable with Playwright on the mock house) is feasible.
- [2026-11-22] DECISION (Charles, stated): prefers the HACS Scheduler card as the editor; it "explicitly says it controls input parameters". Corrects my earlier dismissal [found: scheduler-card README, 2026-11-22]: time schemes give one bar per day-set with draggable timeslots (15 min step), each slot with its own action; the active slot re-fires on create/edit/enable/HA restart; nothing runs at slot end; targets can be automation/script/input_boolean etc. via `include`, and YAML-only `customize` adds a numeric variable (min/max/step) to any service, e.g. input_number set_value. Weekend = inverse of workdays when the Workday integration is installed (holidays become weekend). One action per schedule item, so weekday/weekend = two schedules per room. Still unverified: input_number set_value in the UI; the restart re-fire wiping a manual override.
