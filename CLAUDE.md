# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a **Home Assistant configuration repository** (not a software project) — YAML configuration,
custom components, and automation blueprints for a home automation system. It's config-as-code:
changes are made through YAML edits, not builds or compilation.

**Home Assistant best-practices skill**: `.claude/skills/home-assistant-best-practices/` (vendored
from [homeassistant-ai/skills](https://github.com/homeassistant-ai/skills)) covers native
triggers/conditions vs. templates, helper selection, automation modes, `entity_id` vs `device_id`,
Zigbee patterns, blueprints, and dashboard cards. It loads automatically — consult it before writing
or editing automations, scripts, scenes, blueprints, or dashboards.

## Commands

- Validate YAML syntax: `yamllint *.yaml packages/*.yaml`
  - This checks syntax/style only, not Home Assistant semantics — standard YAML tooling doesn't
    understand HA's custom tags (`!include`, `!secret`, `!include_dir_merge_named`,
    `!include_dir_named`). Full validation requires an HA restart.
- No build or test suite. Home Assistant loads these YAML files directly and validates them on
  restart — that restart happens outside this repo, not as a command you run here.

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
- Editing YAML in this repo takes effect only once the change is merged and pulled onto the live
  instance — see the sync mechanics below.
- Calling the live API takes effect immediately but does **not** touch this repo — UI/API-driven
  changes (helpers, automations created via config flow, entity renames) only show up here after
  `gitsync.sh` next runs `git add . && git commit` inside `/config`.

**How changes move between this repo and the live instance — two mechanisms, one direction each:**
- **Push (live → repo):** `gitsync.sh`, invoked by the "Auto-commit configuration changes"
  automation every 5 minutes, runs `git add .`, `git commit -am`, `git push` inside `/config`.
  It captures UI/API-driven changes. It deliberately does **not** pull.
- **Pull (repo → live):** the **Git pull add-on** watches the remote, pulls merged commits into
  `/config`, and restarts Home Assistant when the config changed in a way that requires it. This
  is what makes a merged PR take effect — you normally do **not** need to call a reload service
  or restart HA yourself after merging.

**Never add `git pull` back into `gitsync.sh`.** It creates a race: if `gitsync.sh` pulls the
remote commits first, the add-on finds nothing new to pull, treats the config as unchanged, and
skips the restart. The merged YAML then sits on disk, live-but-unapplied, until something else
restarts HA. (This bug was live until 2026-07-26 and is why a merged scene change that day landed
on disk without ever taking effect.)

The add-on restarts only when the change warrants it, so *not* observing a restart after a merge
is not by itself evidence that the mechanism is broken.

**Never write `$HA_TOKEN` (or any derived credential) to a file in this repo.** `gitsync.sh` runs
`git add .` across the entire `/config` directory and auto-commits/pushes everything in it — this
repo *is* the live HA config directory, already includes a tracked `secrets.yaml`, and has no
secret-scanning safety net. Keep the token in the process environment only.

## Architecture

### Split configuration

`configuration.yaml` is the root config; it pulls everything else in via `!include`:
- `automations.yaml`, `scripts.yaml`, `scenes.yaml`, `template_sensors.yaml`, `climate.yaml`
- `packages/` (`!include_dir_named`) — package-based config; for anything beyond a single trivial
  entity, group the related helpers/automations/entities into one file here rather than spreading
  them across the top-level files. This is the dominant pattern in this repo (see the TRV section
  below) — check `packages/` first when looking for how an existing feature is wired up.
- `themes/` (`!include_dir_merge_named`) — frontend themes
- Lovelace: `mode: storage` (UI-managed dashboard) plus one YAML dashboard,
  `dashboards/chore-tracking.yaml`

### Custom components (`custom_components/`)

- **`smart_thermostat/`** — PID-based climate control backing the TRV pattern below. Main logic in
  `climate.py` (~1200 lines): platform schema, heater/cooler entities, outdoor sensor support, PID
  algorithm. Constants in `const.py`.
- **`adaptive_lighting/`** — adjusts light color/brightness by time of day. Entry point
  `__init__.py`, main logic `switch.py`, uses a config-flow integration.
- **`hacs/`** — Home Assistant Community Store (package manager); not typically modified directly.

### Zigbee2MQTT

Device config is in `zigbee2mqtt/configuration.yaml`, connected via MQTT (`core-mosquitto:1883`).
The `devices:` section is **auto-managed by Home Assistant/Zigbee2MQTT — never edit it by hand**;
newly paired devices appear there automatically with a `friendly_name`.

### Entity ID types — don't confuse these

1. `entity_id` — human-readable, e.g. `binary_sensor.motion_sensor_kitchen_occupancy`
2. `device_id` — UUID for a physical device, e.g. `bb9532358b487e4b89cfe0e3b76b91e0`
3. `area_id` — room/zone, e.g. `kitchen`, `living_room`

Automation `target:` blocks mix all three depending on context:

```yaml
target:
  area_id: kitchen # All entities in area
  device_id: <uuid> # Specific device
  entity_id: <domain.name> # Specific entity
```

### Automations and blueprints

Standard automation shape (`automations.yaml`):

```yaml
- id: "<timestamp>"
  alias: Human-readable name
  description: ""
  triggers: [...]
  conditions: [...]
  actions: [...]
  mode: restart|single|parallel # Execution mode when retriggered
```

Blueprints live in `blueprints/automation/` and are referenced with `use_blueprint:` + `input:`.

### Template sensors

Jinja2-templated computed states, in `template_sensors.yaml`:

```yaml
- binary_sensor:
    - name: "Anyone Home"
      state: >
        {% set people = [states.person.charles, states.person.gaby, states.person.harry] %}
        {{ people | selectattr('state', 'equalto', 'home') | list | count > 0 }}
```

## TRV PID controller pattern

Each room with PID-controlled TRV heating is a single package file,
`packages/climate_{room_name}.yaml`, containing all of the following (see
`packages/climate_living_room.yaml` for the current reference implementation):

1. **Input Number helper** — `input_number.{room_name}_trv_valve_position`, stores the 0-100 valve
   position the PID controller drives
2. **`smart_thermostat` climate entity** — the PID controller itself, `heater:` pointed at the
   input_number above, `target_sensor:` at the room's external temperature sensor. Current gains
   used across all rooms: `kp: 30`, `ki: 0.005`, `kd: 2000`, `pwm: 0`
3. **Valve sync automation** — blueprint `arnie580/sonoff-trv-pid.yaml`, copies the helper's value
   onto the physical TRV's valve opening/closing degree numbers
4. **External temperature sync automation** — blueprint
   `photomoose/sonoff-trvzb-external-temperature-sensor-calibration.yaml`, feeds the external
   sensor's reading into the TRV's external-temperature input
5. **Two setpoint sync automations** (physical TRV → PID controller, and PID controller → physical
   TRV) — each triggers on the other entity's `temperature` attribute changing, gated by a template
   condition that only fires when the two setpoints actually differ, to avoid an infinite sync loop
6. **Boost mode** — `input_boolean.boost_mode_{room_name}`, `input_datetime.boost_start_{room_name}`,
   a template `button.boost_{room_name}`, and three automations (activate / deactivate / timeout).
   Activating sets the valve to 100% and calls `smart_thermostat.set_pid_mode` with `mode: "off"`;
   the timeout automation polls every 5 minutes and turns boost off once `boost_start` is more than
   an hour old; deactivating restores `mode: "on"`.

Currently implemented for: living room, master bedroom, bedroom (all with boost mode).

To add a new room, copy an existing `packages/climate_{room}.yaml` and rename entities/blueprint
inputs for the new room. Prerequisites: the TRV must be paired in HA, an external temperature
sensor must be available, the TRV must be set to external-sensor mode in Zigbee2MQTT, and the
Smart Thermostat (PID) HACS integration must be installed.

TRV troubleshooting:
- **Not responding** → check the valve sync automation is running
- **Inaccurate temperature** → check the external sensor sync automation is active
- **Enters fail-safe mode** → the external sensor must report at least once every 2 hours
- **Setpoints not syncing** → check both setpoint sync automations are enabled
- **Setpoint sync loop** → the template conditions should prevent this by only firing when the two
  setpoints differ; if it's looping, check that condition first

## Common pitfalls

1. **`device_id` vs `entity_id`** — automations mix these; verify which type a given action expects
2. **YAML indentation** — Home Assistant is strict about 2-space indentation, never tabs
3. **`secrets.yaml`** — git-ignored, exists on the live system but not in this repo; reference
   values with `!secret` (e.g. `api_key: !secret openweather_api_key`) rather than inlining them
4. **Scenes** capture full entity state (brightness, color, etc.), not just on/off
5. **Custom components** are HA integrations, not standalone Python projects — follow the
   async `async_setup_entry()` / `async_unload_entry()` pattern and keep `manifest.json` in sync
