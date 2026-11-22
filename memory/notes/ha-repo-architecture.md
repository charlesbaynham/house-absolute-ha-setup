---
name: ha-repo-architecture
description: Layout of this Home Assistant config repo — root files, packages, custom components, Zigbee2MQTT, automation/blueprint and template-sensor shapes, dashboards. Read when finding where a feature is wired or adding config.
aliases: [repo layout, configuration.yaml, packages, custom components, blueprints, zigbee2mqtt]
updated: 2026-11-22
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
- `scheduler/` — Scheduler component 3.3.9, vendored by hand (PR #111), with one marked local patch
  (PR #112, upstream nielsfaber/scheduler-component #555). Not tracked by the marketplace.
- No `hacs/`: HACS was replaced by HA's built-in `marketplace` integration (config entry on the live
  instance; update + pre-release switch entities for adaptive_lighting, smart_thermostat PID,
  webhook_conversation and the valetudo-map and mini-graph cards). Installed items land in
  `custom_components/` / `www/community/` and are committed by gitsync like everything else.
  [stated: Charles, 2026-11-22] [found: live API, 2026-11-22]

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

## Heating packages and the mock house

`packages/heating_presence.yaml` holds the presence facts the [heating policy](memory/notes/heating-policy.md) reads;
`packages/climate_{room}.yaml` hold each room's PID, helpers and policy instance (details in
[trv-pid-heating](memory/notes/trv-pid-heating.md)). `tests/ha_mock/` is a pytest mock house (a real HA core
running this repo's YAML); it is not loaded by HA. `docs/heating-control-state-machines.md` is the design record.

## Other features with their own docs

- Chore tracking: `packages/chore_tracking.yaml` + `dashboards/chore-tracking.yaml`; the
  `chore-tracking` skill covers it.
- `FAIRY_LIGHTS_DORMANT.md` (repo root): the living-room fairy-lights socket was repurposed as the
  master bedroom fan on 2026-07-26; the old config is kept inert there. [found: that file, 2026-11-08]
