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

- Heating is decided per room by one policy (off / setback / comfort) from presence, back door and
  occupied / switched-off switches; live since 2026-11-10 (PR #106). Look at `input_text.<room>_heating_status`
  for "why". Known open limitation: a stale TRV setpoint after a TRV outage can inflate comfort by 2 °C.

## On the horizon

*(empty)*

## Key learnings & principles

- Test heating/presence changes on the mock house (`tests/ha_mock`) before a PR, then live after the merge.
- Don't spoof `anyone_home` live (vacuum 20 h guard, lights-off automation). Don't write a PID's
  `hvac_mode` from another automation: the policy owns it.

## Tools & resources

- Live API: `$HA_TOKEN` (or the `ha-api-token` skill); entity IDs always looked up live.
- Skills in `.claude/skills/`: `home-assistant-best-practices`, `chore-tracking`, `ha-api-token`,
  `ha-test-harness` (mock house, mutation runner, live-API helpers).
- Repo: `charlesbaynham/house-absolute-ha-setup`, default branch `master`.
- Mock house: `tests/ha_mock` (real HA 2026.10 core + this repo's YAML); design record
  `docs/heating-control-state-machines.md`.
- Notes: [ha-sync-and-deploy](memory/notes/ha-sync-and-deploy.md),
  [ha-repo-architecture](memory/notes/ha-repo-architecture.md),
  [trv-pid-heating](memory/notes/trv-pid-heating.md); investigations in `docs/`.
