# House Absolute — Home Assistant setup

Home Assistant configuration for the house, as config-as-code. This repository is the live
`/config` directory of the instance at https://automation.houseabsolute.co.uk. It is also an agent
memory workspace (built from [memory-workspace](https://github.com/charlesbaynham/memory-workspace),
engine v1.4.0).

- **Source of truth:** the live HA instance. The YAML here is the config, not the facts.
- **Rules for agents:** `WORKSPACE.md` (git flow, live-API rules, how to work on the config) on
  top of the generic contract `AGENTS.md`.
- **Memory:** `memory/digest.md` (loaded every session), `memory/notes/` (one subject each),
  `memory/log.md` (append-only). Filing is `in-session`: whichever session finds 50 unfiled log
  entries files them. Investigation write-ups live in `docs/`.
- **Features on:** memory, auto-mode rules (`automode.json`). Off: Google Sheets, WhatsApp.
- **Session start:** hooks in `.claude/settings.json` (and `.codex/hooks.json`) sync the branch,
  report memory state and engine updates; `CLAUDE.md` imports `AGENTS.md`, `WORKSPACE.md` and the
  digest.
- **Auto-mode:** paste the output of `agent-tools/automode/install.sh --snippet` into the cloud
  environment's setup script once.
- **Update the engine:** `agent-tools/update.sh --check`, then `agent-tools/update.sh`, then commit
  the diff on its own. `agent-tools/` and `AGENTS.md` are overwritten on update; never edit them.

See [docs/agent-ops-notes.md](docs/agent-ops-notes.md) for what running agents in ephemeral
containers has taught us.
