# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Location

**All architectural documentation, conventions, and development guidelines are maintained in:**

`.github/copilot-instructions.md`

This file serves as the single source of truth for both GitHub Copilot and Claude Code to avoid duplication and ensure consistency.

Please read that file for:
- Project architecture and structure
- Configuration patterns and conventions
- Entity ID types and usage
- TRV PID controller setup
- Common tasks and examples
- Troubleshooting guidance

## Claude Code Specific Notes

When working with this Home Assistant configuration repository:

- This is YAML configuration only - there are no build, test, or compile commands
- Use `yamllint *.yaml packages/*.yaml` to validate YAML syntax locally (note: full validation requires Home Assistant restart due to custom tags like `!include` and `!secret`)
- Changes take effect after Home Assistant service restart (not done from this repository)
- When searching for existing patterns or understanding features, check the `packages/` directory first as related config is grouped there

## Live Home Assistant API access

The live instance is reachable at `https://automation.houseabsolute.co.uk`. When the environment
variable `HA_TOKEN` is set (a Home Assistant long-lived access token), you can call the REST API
directly instead of (or in addition to) editing YAML in this repo:

```bash
# Get all entity states
curl -sS -H "Authorization: Bearer $HA_TOKEN" \
  https://automation.houseabsolute.co.uk/api/states

# Call a service (e.g. turn on a light)
curl -sS -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}' \
  https://automation.houseabsolute.co.uk/api/services/light/turn_on
```

**Two distinct change paths — don't conflate them:**
- Editing YAML in this repo requires a commit/push *and* an HA restart (or targeted reload) to take
  effect, per the note above.
- Calling the live API takes effect immediately but does **not** touch this repo — UI/API-driven
  changes (helpers, automations created via config flow, entity renames) only show up here after
  `gitsync.sh` next runs `git add . && git commit` inside `/config`.

**Never write `$HA_TOKEN` (or any derived credential) to a file in this repo.** `gitsync.sh` runs
`git add .` across the entire `/config` directory and auto-commits/pushes everything in it — this
repo *is* the live HA config directory, already includes a tracked `secrets.yaml`, and has no
secret-scanning safety net. Keep the token in the process environment only.

## Names

- **Gaby** is spelled with a single "b". The user dictates messages via voice, which consistently
  mistranscribes this as "Gabby" (double b) — treat "Gabby" in dictated user messages as a
  mistranscription of "Gaby", not a different person.
