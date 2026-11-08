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

<!-- compaction-baseline: fresh workspace -->
- [2026-11-08] DECISION: this repo (house-absolute-ha-setup) set up as a memory workspace from the template, v1.4.0, overlaid onto the existing history rather than via a fresh clone (the repo is the live /config; rm -rf .git was not an option). Charles's call.
- [2026-11-08] DECISION: project (no end date); owner Charles only, no co-users; source of truth is the live HA instance. Charles's answers in onboarding.
- [2026-11-08] DECISION: memory_filing in-session (threshold 50), Sheets off, WhatsApp off, auto-mode on, Claude Code + Codex wired, track pinned, default branch master. All Charles's choices; recommended defaults taken except in-session filing, which he chose over the recommended scheduled.
- [2026-11-08] DECISION: git flow split by path — memory/ and docs-only changes straight to master; HA behaviour changes (YAML, packages, blueprints, custom_components, zigbee2mqtt, dashboards) via PR. Charles chose this over the contract's commit-everything-to-default-branch; recorded in WORKSPACE.md.
- [2026-11-08] DECISION: the old CLAUDE.md was triaged: standing rules to WORKSPACE.md, architecture/sync/TRV facts to memory/notes/. Charles asked for the triage; the split itself is my judgement.
- [2026-11-08] DECISION: automode.json has an environment sentence only. The template's rules were all WhatsApp-specific; I added no allow/deny rules (suggestion: add some if unattended HA API calls get blocked).
- [2026-11-08] RESOURCE: repo https://github.com/charlesbaynham/house-absolute-ha-setup (visibility assumed private, unchecked).
- [2026-11-08] OPEN: paste `agent-tools/automode/install.sh --snippet` into the cloud environment's setup script (only Charles can); automode-check reports drift until then.
- [2026-11-08] OPEN: unverified whether a pull of memory-only changes makes the Git pull add-on restart HA; check on the first memory-only merge. gitsync.sh will also commit memory/ from the live box.
- [2026-11-08] OPEN: git-sync.sh hook moves sessions onto master at session start once workspace.yaml exists, which conflicts with harness claude/* branches for HA-YAML PR work; untested here.
- [2026-11-08] OPEN: assessed blueprinting packages/climate_{living_room,bedroom,master_bedroom}.yaml (3 near-identical 288-line files; only slug differs, plus master's one-off 4am automation). Feasible for the 7 per-room automations (setpoint sync x2, apply smart mode, boost x3) -> 1 blueprint; NOT feasible for helpers, template button, smart_thermostat climate (blueprints are automation/script/template only). Not started; awaiting Charles's go-ahead. Roll out one room first (heating, winter). back_door.yaml refs automation.<room>_trv_apply_smart_mode, climate_away_mode.yaml also hardcodes per-room lists.
- [2026-11-08] DECISION: Charles asked to migrate all three climate rooms at once onto new blueprint charlesbaynham/trv-room-control.yaml (replaces setpoint x2/apply-smart-mode/boost x3 automations; new automations '<Room> TRV - control', ids 1790000000011-13; deactivate-boost dropped as redundant with smart-mode branch on boost off). back_door.yaml now triggers automation.<room>_trv_control manually to re-apply smart mode. Old automation registry entries become orphans to delete in the UI. PR on branch claude/climate-packages-duplication-iejqv2.
- [2026-11-08] STATE: PR #102 merged — all three climate rooms now run on blueprint trv-room-control.yaml (automations '<Room> TRV - control'). Pending (Charles): post-merge smoke test per room (boost, both setpoint directions, smart mode/parked, back door) and delete the orphaned old automation entities in the UI.
- [2026-11-08] STATE: post-merge live check (HA 2026.10.0, restarted 20:16Z): 3 *_trv_control automations on and firing, old per-room automations 'unavailable' (orphans, Charles to delete). Back door test passed via faked sensor state: pause -> PIDs off, close -> all 3 back to heat and control automation triggered. Smart mode off in all rooms (valves parked at 0) since at least 2026-11-07, unchanged by the migration. Boost/setpoint-sync/smart-mode branches NOT yet live-tested.
- [2026-11-08] LEARNED: a sensor event can be faked without touching hardware: POST /api/states/<entity_id> with {state, attributes} (same as dev-tools 'set state'); the real sensor overwrites it on its next report. Used on binary_sensor.backdoor_sensor_contact; restore the real state afterwards.
- [2026-11-08] STATE: live-tested trv-room-control on living room (setpoint sync both ways, smart on/off, boost on/off, boost timeout via backdated boost_start, parked change, manual trigger): all branches behave as designed; room restored to start state (sp 23, smart off, boost off, valve 0, PID output frozen at 0).
- [2026-11-08] LEARNED: smart_thermostat with pid_mode off keeps writing its frozen last output to the heater helper on every 60s keep_alive, so boost (valve 100) and the parked position get overwritten within <=60s; pre-existing (seen at 12:52 history). Rooms only look fine now because frozen output is 0. Fix candidate: separate pid_output helper + blueprint derives valve helper. OPEN: Charles to decide. See trv-pid-heating note.
- [2026-11-08] DECISION: Charles approved the fix for boost/parked being overwritten by the PID keep-alive: PID heater is now input_number.<room>_trv_pid_output; blueprint trv-room-control is sole writer of the valve helper (off->0, boost->100, smart->PID output, else parked). Branch claude/climate-packages-duplication-iejqv2-valve; validated with HA 2026.10 schema + 23-check simulation in a real HA core (pip homeassistant==2026.10.0 needs python 3.14 via uv).
- [2026-11-08] STATE: PR #103 merged (PID heater -> <room>_trv_pid_output; blueprint sole writer of valve helper). Pending: live re-test on living room after the HA restart (boost holds >2min, parked 10 holds, back-door pause/resume).
- [2026-11-08] STATE: PR #103 verified live on the living room (HA 2026.10.0): boost held 100 for 200s (old bug reverted it in ~15s), parked 10 held >100s, smart mode follows <room>_trv_pid_output, TRV<->PID setpoint sync both ways, fake back-door open/close incl. during boost (valve 0 while open, restored on close). Room restored (sp 23, smart off, boost off, valve 0). Bedroom and master bedroom not exercised, same blueprint.
- [2026-11-08] STATE: deleted the 18 orphaned old per-room automation entities (setpoint sync x2, apply smart mode, boost activate/deactivate/timeout; 3 rooms) from the live entity registry via websocket config/entity_registry/remove, after checking each was unavailable+restored. Other unavailable automations remain, not from this work: living_room_cosy_button, climate_turn_off_pid_controllers_when_both_far_away, climate_turn_on_pid_controllers_when_someone_returns, master_bedroom_lights_copy_main, turn_bathroom_lights_on_when_gaby_wakes_up, bathroom_motion, lights_motion_living_room, master_bedroom_sync_state_when_all_lights_off / _when_main_lights_on.
