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

*(empty)*

## On the horizon

*(empty)*

## Key learnings & principles

*(empty)*

## Tools & resources

- Live API: `$HA_TOKEN` (or the `ha-api-token` skill); entity IDs always looked up live.
- Skills in `.claude/skills/`: `home-assistant-best-practices`, `chore-tracking`, `ha-api-token`.
- Repo: `charlesbaynham/house-absolute-ha-setup`, default branch `master`.
- Notes: [ha-sync-and-deploy](memory/notes/ha-sync-and-deploy.md),
  [ha-repo-architecture](memory/notes/ha-repo-architecture.md),
  [trv-pid-heating](memory/notes/trv-pid-heating.md); investigations in `docs/`.
