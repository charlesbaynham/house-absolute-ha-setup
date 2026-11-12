# WORKSPACE.md — what this workspace is for, and its own rules

## What this is for

Charles's Home Assistant configuration for the house: YAML, custom components and automation
blueprints, kept as config-as-code. Not a software project — no build, no test suite. Open-ended
(no end date). This repo **is** the live `/config` directory of the running instance, so what is
merged here is what runs the house.

Memory (`memory/`) holds the durable knowledge around the config: how it is wired, why it is that
way, what was investigated. `docs/` keeps the investigation write-ups agents have already filed
there (index: `docs/README.md`); read the relevant one before working on its topic.

## Who is who

- **Charles** — owner; technical; terse. Expert Python/C++/ARTIQ; does not need things
  over-explained.

No co-users. Household members (HA person entities `charles`, `gaby`, `harry`) do not use this
workspace.

## Source of truth

The **live HA instance**, `https://automation.houseabsolute.co.uk`. This repo's YAML is the
config, not the facts: entities defined here may not exist live (a platform that failed to load, a
device repurposed). Facts about entity states and IDs are re-read live every time.

- **Never guess an entity ID.** Look it up in `/api/states` before using it in YAML or a service
  call — not inferred from Z2M friendly names, other rooms' naming, or the repo. Say so if one
  doesn't exist.
- Token: `$HA_TOKEN`, else fetch it with the `ha-api-token` skill. **Never write it (or anything
  derived) to a file in this repo** — `gitsync.sh` runs `git add .` on all of `/config` and
  auto-commits and pushes it, and there is no secret scanning.
- `secrets.yaml` is git-ignored and exists only live; reference values with `!secret`.

Two change paths, not to be conflated:
- **Edit YAML here** — takes effect once merged and pulled onto the instance (the Git pull
  add-on pulls and restarts HA if needed; do not call a reload or restart yourself after a merge).
  Not seeing a restart after a merge is not by itself a sign the mechanism is broken.
- **Call the live API** — immediate, but touches nothing here; UI/API changes reach this repo
  only when `gitsync.sh` next commits `/config` (every 5 minutes).

**Never add `git pull` to `gitsync.sh`.** It races the add-on: if gitsync pulls first, the add-on
finds nothing new, skips the restart, and merged YAML sits on disk unapplied. (Bug live until
2026-07-26.) See [memory/notes/ha-sync-and-deploy.md](memory/notes/ha-sync-and-deploy.md).

## Git flow — overrides the contract's "commit straight to the default branch"

Charles's decision (2026-11-08), split by path. The default branch is `master`.

- **`memory/` and docs-only changes** (`docs/`, `WORKSPACE.md`, `CLAUDE.md`, notes): commit and
  push straight to `master`, as `AGENTS.md` says.
- **Anything that changes Home Assistant behaviour** (YAML, `packages/`, `blueprints/`,
  `custom_components/`, `zigbee2mqtt/`, `dashboards/`): branch, commit, open a PR; do not push to
  `master`. Merging applies it live.
- A harness-supplied `claude/…` branch is fine for that PR flow. For memory/docs-only work follow
  `AGENTS.md` (go to `master`).
- `gitsync.sh` also commits and pushes `/config` from the live box; a rejected push there is
  expected while the remote is ahead and fixes itself.

## How to work on the config

- **Consult the `home-assistant-best-practices` skill** (`.claude/skills/`) before writing or
  editing automations, scripts, scenes, blueprints or dashboards. Other skills: `chore-tracking`
  (editing `packages/chore_tracking.yaml` or its dashboard), `ha-api-token`, `ha-test-harness`
  (the mock house, mutation testing and the live-API helpers for post-merge simulations).
- Validate syntax with `yamllint *.yaml packages/*.yaml`. That checks YAML only; HA's custom tags
  (`!include`, `!secret`, …) and semantics are validated on restart, which happens outside this
  repo.
- **Prefer a package** (`packages/<feature>.yaml`) for anything beyond one trivial entity: helpers,
  automations and entities for a feature in one file. Check `packages/` first when asking how a
  feature is wired.
- 2-space indentation, never tabs. Don't confuse `entity_id`, `device_id` (UUID) and `area_id`;
  check which an action expects. Scenes capture full entity state, not just on/off.
- `zigbee2mqtt/configuration.yaml`: the `devices:` section is auto-managed — never edit by hand.
- Custom components are HA integrations, not standalone Python: follow the async
  `async_setup_entry()` / `async_unload_entry()` pattern and keep `manifest.json` in sync. `hacs/`
  is not modified directly.
- Adding or changing TRV heating for a room: read
  [memory/notes/trv-pid-heating.md](memory/notes/trv-pid-heating.md) first.
- **Heating and presence logic is tested on the mock house before a PR**: `tests/ha_mock` runs a real HA
  core with this repo's YAML (README there). Restarts, debounces and race conditions are what it is for.

## Anything user-facing needs an area (Charles, 2026-11-12)

Charles's standing rule: every entity a person is meant to see or operate (a switch, setpoint,
status text, boost or smart-mode toggle, a room's helpers) **must be assigned to an area**. The main
dashboards (Overview, Home, Areas) are generated by area strategies, and Overview sets
`hide_entities_without_area`, so an entity with no area is invisible there. Internal plumbing (PID
output, last-written / start-time helpers, debounce latches) stays area-less on purpose.

YAML cannot carry an area for helpers, so this is a **live registry step after the merge** that adds
the entity: websocket `config/entity_registry/update` with `area_id` (or Settings > Entities). Then
list the registry and confirm nothing user-facing is left with `area_id: null`. A PR that adds a
user-facing entity is not done until this has been checked. The areas are not in the repo (they live
in the instance's `.storage`).

## After a merge: test it live

Charles's standing instruction (2026-11-09): after a change that alters Home Assistant behaviour
is merged and live, **simulate the states and test it through the live API without being asked**.
If the test would be disruptive (e.g. it would really move heating for the whole house, trigger
alarms, locks, or notify people), offer it to Charles instead; he may say yes anyway. Snapshot the
affected entities first, restore everything in a `finally`, and report what passed and what could
not be exercised. Check who else is home before spoofing any presence entity, and **do not spoof
`binary_sensor.anyone_home` live**: it drives the heating policy (setback) and also arms "Vacuum when
everyone leaves" (a 20 h `last_triggered` guard, so a spoofed trip blocks the real run) and "Turn off all
lights when everyone leaves". Test those rules on the mock house instead.

## Scheduling waits and check-ins

A scheduled wait (`send_later`, wakeups) is **slightly under an hour** (55 minutes) so the prompt
cache stays warm; only genuinely multi-hour waits are exempt. No repeating PR check-ins — rely on
the PR subscription.

## Notes and docs

Durable cross-session knowledge goes in `memory/notes/` (see `AGENTS.md`). Investigation
write-ups (a bug, a design decision, why config is as it is) may continue in `docs/<topic>.md` with
an entry in `docs/README.md`: verified facts, dated and with how checked, kept apart from
hypotheses. Never put tokens or secrets in either.

## Things that always go to the owner

*(none yet — the owner adds these as they arise)*
