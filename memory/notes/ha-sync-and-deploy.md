---
name: ha-sync-and-deploy
description: How changes move between this repo and the live Home Assistant instance (gitsync.sh push, Git pull add-on pull + restart), and the live API access. Read before assuming a merge is or isn't live, or touching gitsync.sh.
aliases: [gitsync, git pull add-on, deploy, live instance, HA API]
updated: 2026-11-08
---

# Repo ↔ live instance

Migrated from the old `CLAUDE.md` on 2026-11-08; provenance `[found: CLAUDE.md, 2026-11-08]`.
The rules that bind agents (never guess entity IDs, never write `$HA_TOKEN` to a file, never add
`git pull` to `gitsync.sh`) are in `WORKSPACE.md`, not here.

## Two mechanisms, one direction each

- **Live → repo (push).** `gitsync.sh`, run by the "Auto-commit configuration changes" automation
  every 5 minutes, does `git add .`, `git commit -am`, `git push` inside `/config`. Captures
  UI/API-driven changes (helpers, config-flow automations, entity renames). Deliberately does not
  pull. [found: CLAUDE.md, 2026-11-08]
- **Repo → live (pull).** The **Git pull add-on** watches the remote, pulls merged commits into
  `/config`, and restarts HA when the config changed in a way that needs it. A merged PR takes
  effect this way; no manual reload or restart is normally needed. [found: CLAUDE.md, 2026-11-08]
- Why gitsync must not pull: if it pulls first, the add-on finds nothing new, treats the config as
  unchanged and skips the restart; merged YAML sits live-on-disk but unapplied. This bit on
  2026-07-26 — a merged scene change never took effect. [found: CLAUDE.md, 2026-11-08]
- Consequence: gitsync's push is rejected while the remote is ahead (just after a merge). Expected;
  the add-on pulls and the next run pushes cleanly. [found: gitsync.sh comments]
- No restart observed after a merge is not itself evidence the mechanism is broken — the add-on
  restarts only when warranted.

## Live API

`https://automation.houseabsolute.co.uk`, with a long-lived token in `$HA_TOKEN` (else the
`ha-api-token` skill fetches it from the Secrets MCP). Useful calls:

```bash
curl -sS -H "Authorization: Bearer $HA_TOKEN" https://automation.houseabsolute.co.uk/api/states
curl -sS -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' \
  https://automation.houseabsolute.co.uk/api/services/light/turn_on
```

API calls take effect immediately and do not touch the repo; they appear here only after
`gitsync.sh` next commits `/config`.

## Workspace overlay (added 2026-11-08)

The memory-workspace files (`memory/`, `agent-tools/`, `AGENTS.md`, `WORKSPACE.md`) live in this
same `/config` tree, so gitsync commits them too. [inferred] Whether a pull that changes only
those files triggers an HA restart is not verified — check on the first memory-only merge.
