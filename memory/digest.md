# Memory digest

<!--
Rewritten by the memory-compact skill's filing pass. Imported into every
session, so keep it to 500 words or fewer: depth goes in memory/notes/, which
the SessionStart hook indexes. Link a note (ordinary Markdown, never `@`) only
where a line here depends on it.
-->

## Purpose & context

Charles's Home Assistant config for the house, as config-as-code. This repo is the live `/config`
directory (instance at automation.houseabsolute.co.uk): merged YAML runs the house. A project with
no end date. Rules and git flow are in `WORKSPACE.md`; layout, deploy mechanics and the TRV heating
pattern are in `memory/notes/`.

## Current state

- Heating is decided per room by one [policy](memory/notes/heating-policy.md) (off / setback / comfort) from presence, back door and
  occupied / switched-off switches; live since 2026-11-10 (PR #106). Look at `input_text.<room>_heating_status`
  for "why". Echo guard: a PID setpoint differing from the policy's last write within 10 s is an echo, not an edit (PR #108, live
  2026-11-14; a presence flicker had inflated comfort by 2 °C on 2026-11-13, see [heating-policy](memory/notes/heating-policy.md)).
  Open: an echo later than 10 s (TRV outage) can still inflate comfort.
- Smart mode is on in all three rooms (live 2026-11-13; it was off until at least 2026-11-12), so the PID's
  demand reaches the valves again (see [trv-pid-heating](memory/notes/trv-pid-heating.md)).

## On the horizon

- Scheduler: stay on the vendored copy (`custom_components/scheduler`, with a local rename-bug patch, PR #112) until
  upstream nielsfaber/scheduler-component PR #555 is merged and released; then move to the marketplace version and
  drop the vendored copy (Charles, stated 2026-11-22). Check marketplace can install it first.

## Key learnings & principles

- Test heating/presence changes on the mock house (`tests/ha_mock`) before a PR, then live after the merge.
- Lighting uses only motion sensors, never the heating `occupied` state (Charles, stated).
- Don't spoof `anyone_home` live (vacuum 20 h guard, lights-off automation). Don't write a PID's
  `hvac_mode` from another automation: the policy owns it.

## Tools & resources

- Live API: `$HA_TOKEN` (or the `fetching-secrets` skill); entity IDs always looked up live.
- Skills in `.claude/skills/`: `home-assistant-best-practices`, `chore-tracking`, `fetching-secrets`,
  `ha-test-harness` (mock house, mutation runner, live-API helpers).
- Repo: `charlesbaynham/house-absolute-ha-setup` (public on GitHub), default branch `master`.
- Mock house: `tests/ha_mock` (real HA 2026.10 core + this repo's YAML); design record
  `docs/heating-control-state-machines.md`.
- Notes: [ha-sync-and-deploy](memory/notes/ha-sync-and-deploy.md),
  [ha-repo-architecture](memory/notes/ha-repo-architecture.md),
  [trv-pid-heating](memory/notes/trv-pid-heating.md); investigations in `docs/`.
