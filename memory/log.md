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
