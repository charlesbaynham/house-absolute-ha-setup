---
name: ha-sync-and-deploy
description: How changes move between this repo and the live Home Assistant instance (gitsync.sh push, Git pull add-on pull + restart), and the live API access. Read before assuming a merge is or isn't live, or touching gitsync.sh.
aliases: [gitsync, git pull add-on, deploy, live instance, HA API]
updated: 2026-11-13
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
`fetching-secrets` skill fetches it from the Secrets MCP). Useful calls:

```bash
curl -sS -H "Authorization: Bearer $HA_TOKEN" https://automation.houseabsolute.co.uk/api/states
curl -sS -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' \
  https://automation.houseabsolute.co.uk/api/services/light/turn_on
```

API calls take effect immediately and do not touch the repo; they appear here only after
`gitsync.sh` next commits `/config`.

### Live-test techniques

- `[found: live, 2026-11-08]` `POST /api/states/<entity_id>` with `{state, attributes}` sets an entity's state in
  the state machine (like dev-tools "set state"), fires automations and leaves the hardware alone; the real
  sensor overwrites it on its next report. Template sensors using `now()` re-render about every minute, so a
  spoof of one (e.g. `binary_sensor.charles_confirmed_away`) lasts under 60 s. Restore by POSTing the original.
- `[found: live, 2026-11-09]` REST calls made with the long-lived token carry a user context (`user_id` set);
  automation actions do not. By-hand rules (override, switched-off switch) depend on that difference.
- `[found: live, 2026-11-09]` Spoofing `person.*` while nobody else is home really flips `anyone_home` and runs
  presence automations (it did, because Gaby left mid-test). Do not blind-restore a climate setpoint afterwards:
  the cleanup left a room 2 degC wrong until corrected.
- `[found: session, 2026-11-12]` From a cloud session, a Python `websockets` client needs `proxy=None` (and
  `NO_PROXY='*'`), else the agent proxy gives a bare 502; HA at 10.0.1.2:8123 was reachable only after
  tailscale was up. Registry changes use websocket `config/entity_registry/{update,remove}`.
- `[found: live, 2026-11-13]` `/api/history/period` over a 4-day window returned only about the first half of the
  data; 1.5 days was complete. To ask "does the master bedroom heating flap?", read
  `binary_sensor.charles_away_for_heating` (the latched sensor the policy follows) and
  `input_text.master_bedroom_heating_status`, not the raw `charles_confirmed_away`.
- Scripts for all of this are in the `ha-test-harness` skill.

## Workspace overlay (added 2026-11-08)

The memory-workspace files (`memory/`, `agent-tools/`, `AGENTS.md`, `WORKSPACE.md`) live in this
same `/config` tree, so gitsync commits them too. [inferred] Whether a pull that changes only
those files triggers an HA restart is not verified — check on the first memory-only merge.
- `[found: list_repos, 2026-11-11]` `charlesbaynham/house-absolute-ha-setup` is a **public** GitHub repository
  (the workspace setup had assumed private); everything in `memory/` and `docs/` is world-readable.
- `[found: session, 2026-11-08]` Open: `agent-tools/automode/install.sh --snippet` output was to be pasted into the
  cloud environment's setup script by Charles; `automode-check` reports drift until then.
