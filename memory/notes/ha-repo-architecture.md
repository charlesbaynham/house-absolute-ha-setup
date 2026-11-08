---
name: ha-repo-architecture
description: Layout of this Home Assistant config repo — root files, packages, custom components, Zigbee2MQTT, automation/blueprint and template-sensor shapes, dashboards. Read when finding where a feature is wired or adding config.
aliases: [repo layout, configuration.yaml, packages, custom components, blueprints, zigbee2mqtt]
updated: 2026-11-08
---

# Repo architecture

Migrated from the old `CLAUDE.md` on 2026-11-08; `[found: CLAUDE.md, 2026-11-08]` throughout.
Config-as-code: YAML edits, no build. Home Assistant validates on restart.

## Split configuration

`configuration.yaml` is the root and pulls in:
- `automations.yaml`, `scripts.yaml`, `scenes.yaml`, `template_sensors.yaml`, `climate.yaml`
- `packages/` via `!include_dir_named` — the dominant pattern; related helpers, automations and
  entities for a feature in one file (see the TRV rooms: [trv-pid-heating](memory/notes/trv-pid-heating.md))
- `themes/` via `!include_dir_merge_named`
- Lovelace: `mode: storage` (UI-managed) plus YAML dashboards in `dashboards/`:
  `chore-tracking.yaml` and `charles-alarm.yaml` [found: repo listing, 2026-11-08] (the old
  CLAUDE.md said only the first); both are registered in `configuration.yaml`

## Custom components (`custom_components/`)

- `smart_thermostat/` — PID climate control behind the TRV pattern. Logic in `climate.py`
  (~1200 lines: platform schema, heater/cooler entities, outdoor sensor, PID); constants in
  `const.py`.
- `adaptive_lighting/` — colour/brightness by time of day; config-flow integration. `__init__.py`
  entry, `switch.py` logic.
- `hacs/` — HACS package manager; not modified directly.

## Zigbee2MQTT

`zigbee2mqtt/configuration.yaml`, connected via MQTT (`core-mosquitto:1883`). The `devices:`
section is auto-managed by HA/Z2M; new devices appear with a `friendly_name`.

## IDs

`entity_id` (`binary_sensor.motion_sensor_kitchen_occupancy`), `device_id` (UUID), `area_id`
(`kitchen`). `target:` blocks mix all three by context.

## Automations and blueprints

`automations.yaml` shape: `id` (timestamp string), `alias`, `description`, `triggers`,
`conditions`, `actions`, `mode` (`restart|single|parallel`). Blueprints are in
`blueprints/automation/`, used with `use_blueprint:` + `input:`.

## Template sensors

Jinja2 computed states in `template_sensors.yaml`, e.g. the "Anyone Home" binary sensor counting
`person.charles`, `person.gaby`, `person.harry` in state `home`.

## Other features with their own docs

- Chore tracking: `packages/chore_tracking.yaml` + `dashboards/chore-tracking.yaml`; the
  `chore-tracking` skill covers it.
- `FAIRY_LIGHTS_DORMANT.md` (repo root): the living-room fairy-lights socket was repurposed as the
  master bedroom fan on 2026-07-26; the old config is kept inert there. [found: that file, 2026-11-08]
