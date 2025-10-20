# Home Assistant Configuration - AI Agent Guide

## Project Overview

This is a **Home Assistant configuration repository** (not a development project). It contains YAML configuration files, custom components, and automation blueprints for a home automation system.

**Key principle**: This is a configuration-as-code setup. Changes should be made through YAML edits, not code compilation or builds.

## Architecture & Structure

### Core Configuration Pattern

- **Split configuration**: `configuration.yaml` uses `!include` directives to modularize configs:
  - `automations.yaml` - automation rules
  - `scripts.yaml` - reusable action sequences
  - `scenes.yaml` - scene definitions (lighting states, etc.)
  - `template_sensors.yaml` - Jinja2 template-based sensors
- All configs use YAML format; Home Assistant validates and loads them on restart

### Custom Components

Located in `custom_components/`, these are Python-based integrations:

1. **`adaptive_lighting/`** - Adjusts light color/brightness based on time of day

   - Entry point: `__init__.py`, main logic: `switch.py`
   - Uses config flow pattern with translations support

2. **`smart_thermostat/`** - PID-based climate control

   - Main implementation: `climate.py` (~1200 lines)
   - Supports heater/cooler entities, outdoor sensors, and PID algorithms
   - Platform schema in `climate.py`, domain constants in `const.py`

3. **`hacs/`** - Home Assistant Community Store (package manager)
   - Complex structure with repositories/, websocket/, validate/ subdirectories
   - Not typically modified directly

### Integration Points

- **Zigbee2MQTT**: Configuration in `zigbee2mqtt/configuration.yaml`
  - Connects via MQTT broker (core-mosquitto:1883)
  - Device definitions include friendly names (e.g., TRVs, Hue switches)
- **Blueprints**: Reusable automation templates in `blueprints/automation/`
  - Used via `use_blueprint:` in automations (see lines 39-41, 183-185 in `automations.yaml`)

## Key Conventions

### Entity Identification Pattern

Home Assistant uses three distinct ID types - **never confuse them**:

1. **`entity_id`**: Human-readable identifier (e.g., `binary_sensor.motion_sensor_kitchen_occupancy`)
2. **`device_id`**: UUID for physical devices (e.g., `bb9532358b487e4b89cfe0e3b76b91e0`)
3. **`area_id`**: Zone identifier for rooms (e.g., `living_room`, `kitchen`)

**Pattern**: Automations use all three types depending on context. When targeting actions:

```yaml
target:
  area_id: kitchen # All entities in area
  device_id: <uuid> # Specific device
  entity_id: <domain.name> # Specific entity
```

### Automation Structure

Standard automation format (see `automations.yaml`):

```yaml
- id: "<timestamp>"
  alias: Human-readable name
  description: ""
  triggers: [...]
  conditions: [...]
  actions: [...]
  mode: restart|single|parallel # Execution mode when retriggered
```

### Blueprint Usage

Reference blueprints with `use_blueprint:` and provide `input:` parameters:

```yaml
use_blueprint:
  path: homeassistant/motion_light.yaml
  input:
    motion_entity: binary_sensor.living_room_motion_occupancy
    light_target:
      area_id: living_room
```

### Template Sensors

Use Jinja2 templates for computed states (see `template_sensors.yaml`):

```yaml
- binary_sensor:
    - name: "Anyone Home"
      state: >
        {% set people = [states.person.charles, states.person.gaby, states.person.harry] %}
        {{ people | selectattr('state', 'equalto', 'home') | list | count > 0 }}
```

## Development Workflow

### No Build/Test Commands

- **There is no build step** - YAML configs are loaded directly by Home Assistant
- **Testing**: Changes are validated by restarting Home Assistant (not done from this repo)
- **Validation**: Home Assistant checks YAML syntax on startup

### Configuration Changes

1. Edit YAML files directly
2. Restart Home Assistant service (done via HA UI/CLI, not here)
3. Check logs for validation errors

### Custom Component Development

If modifying Python components in `custom_components/`:

- Follow Home Assistant's component architecture (async pattern)
- Use `homeassistant.helpers` for entity management
- Components must have `manifest.json` with domain, version, dependencies
- Entry points: `async_setup_entry()`, `async_unload_entry()`

### Git Workflow

Per `.gitignore`:

- Excludes runtime files: `*.db`, `*.log`, `.storage/`, `.cloud/`
- Version control includes: YAML configs, custom components, blueprints

## Critical Files Reference

- **`configuration.yaml`**: Root config with integration settings and includes
- **`automations.yaml`**: All automation rules (539 lines, heavily used)
- **`zigbee2mqtt/configuration.yaml`**: Zigbee device mappings and MQTT connection
- **`custom_components/smart_thermostat/climate.py`**: PID thermostat implementation
- **`blueprints/`**: Automation templates (motion lights, Hue dimmer patterns)

## Common Pitfalls

1. **Device ID vs Entity ID**: Automations mix these - verify which type an action expects
2. **YAML Indentation**: Home Assistant is strict about 2-space indentation
3. **Secrets**: `secrets.yaml` exists but isn't version controlled - handle carefully
4. **Scene States**: Scenes in `scenes.yaml` capture full entity states (brightness, color, etc.)
5. **Custom Components**: Don't treat these as regular Python projects - they're HA integrations

## When Making Changes

- **Adding automations**: Append to `automations.yaml` with unique ID (timestamp-based)
- **New devices**: Add to `zigbee2mqtt/configuration.yaml` under `devices:` with friendly names
- **Template sensors**: Add to `template_sensors.yaml` following existing sensor structure
- **Custom component changes**: Modify Python files but maintain async patterns and manifest.json version
