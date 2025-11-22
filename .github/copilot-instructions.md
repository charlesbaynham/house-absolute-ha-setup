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

### Local YAML Validation

Before committing changes, validate YAML syntax locally:

```bash
# Validate YAML syntax with yamllint (if available)
yamllint *.yaml

# Note: Standard Python YAML parsing won't work due to Home Assistant-specific tags
# Home Assistant uses custom tags like !include, !secret, !include_dir_merge_named
# Only Home Assistant itself can fully validate these files
```

**Note**: `yamllint` checks syntax and style but not Home Assistant-specific semantics. Full validation requires Home Assistant restart.

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

### Security Best Practices

**Secrets Management**:
- Never commit secrets to `secrets.yaml` 
- Use `!secret` directive in YAML files to reference values from `secrets.yaml`
- Example in configuration: `api_key: !secret openweather_api_key`
- The `secrets.yaml` file is git-ignored - document required secret keys separately

**Sensitive Data**:
- Device IDs and area names are safe to commit
- Don't commit: API keys, passwords, tokens, location coordinates
- Review diffs before committing to catch accidental secret exposure

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
- **New devices**: Will be added by home assistant to `zigbee2mqtt/configuration.yaml` under `devices:` with friendly names. Do not modify this section - it's controlled by Home Assistant. 
- **Template sensors**: Add to `template_sensors.yaml` following existing sensor structure
- **Custom component changes**: Modify Python files but maintain async patterns and manifest.json version

## Common Tasks Examples

### Adding a New Automation

```yaml
# Append to automations.yaml
- id: '1698765432123'  # Use current timestamp
  alias: Turn on kitchen lights at sunset
  description: ''
  triggers:
    - platform: sun
      event: sunset
      offset: '-00:30:00'
  conditions: []
  actions:
    - action: light.turn_on
      metadata: {}
      data: {}
      target:
        entity_id: light.kitchen_lights
  mode: single
```

### Adding a Template Sensor

```yaml
# Add to template_sensors.yaml
- binary_sensor:
    - name: "Kitchen Occupied"
      state: >
        {{ is_state('binary_sensor.motion_sensor_kitchen_occupancy', 'on') }}
      device_class: occupancy
```

### Zigbee Devices

Will be added by Home Assistant automatically. Example entry:
```yaml
# In zigbee2mqtt/configuration.yaml under devices:
'0x00158d0001234567':
  friendly_name: 'kitchen_motion_sensor'
```

Do not add these yourself: this section is managed by Home Assistant and lists the devices available via Zigbee2MQTT.

## Troubleshooting

**YAML Syntax Errors**:
- Check indentation (must be 2 spaces, never tabs)
- Verify quotes around special characters
- Use `yamllint` to identify issues

**Automation Not Triggering**:
- Verify entity_id exists and is correct format (domain.name)
- Check trigger conditions are met
- Review Home Assistant logs for errors

**Device Not Found**:
- Confirm device is in `zigbee2mqtt/configuration.yaml` with correct friendly_name
- Verify entity_id matches pattern: `<domain>.<friendly_name>_<attribute>`
- Check Home Assistant has discovered the Zigbee2MQTT device

## TRV PID Controller Setup Pattern

This section describes the standardized pattern for setting up a TRV (Thermostatic Radiator Valve) with PID control in a room.

### Overview

Each room with TRV PID control requires the following components:

1. **Input Number Helper** - Stores valve position (0-100) controlled by PID
2. **Climate Entity** - Smart thermostat with PID controller
3. **Valve Sync Automation** - Syncs PID output to TRV valve position
4. **External Temperature Sync Automation** - Syncs external sensor to TRV

### Complete Setup Template

#### 1. Input Number Helper (configuration.yaml)

Add to the `input_number:` section:

```yaml
input_number:
  {room_name}_trv_valve_position:
    name: {Room Name} TRV Valve Position
    initial: 0
    min: 0
    max: 100
    step: 1
```

**Example:**
```yaml
input_number:
  living_room_trv_valve_position:
    name: Living room TRV Valve Position
    initial: 0
    min: 0
    max: 100
    step: 1
```

#### 2. Climate Entity (climate.yaml)

Add to the climate configuration file:

```yaml
- platform: smart_thermostat
  name: {Room Name} TRV PID controller
  unique_id: trv_pid_{room_name}
  heater: input_number.{room_name}_trv_valve_position
  target_sensor: sensor.sensor_{room_name}_temperature
  min_temp: 7
  max_temp: 28
  ac_mode: False
  target_temp: 19
  keep_alive:
    seconds: 60
  kp: 60
  ki: 0.01
  kd: 2000
  pwm: 0
```

**Example:**
```yaml
- platform: smart_thermostat
  name: Living room TRV PID controller
  unique_id: trv_pid_living_room
  heater: input_number.living_room_trv_valve_position
  target_sensor: sensor.sensor_living_room_temperature
  min_temp: 7
  max_temp: 28
  ac_mode: False
  target_temp: 19
  keep_alive:
    seconds: 60
  kp: 60
  ki: 0.01
  kd: 2000
  pwm: 0
```

#### 3. Valve Position Sync Automation (automations.yaml)

Create an automation using the `arnie580/sonoff-trv-pid` blueprint:

```yaml
- id: '{unique_id}'
  alias: {Room Name} TRV - sync valve with helper
  description: 'Copy the settings from the 0 - 100 helper to the TRV valve position. This will be controlled by a PID controller from Smart thermostat (PID) - see the YAML.'
  use_blueprint:
    path: arnie580/sonoff-trv-pid.yaml
    input:
      thermostat_value: input_number.{room_name}_trv_valve_position
      max_valve_opening: number.trv_{room_name}_valve_opening_degree
      max_valve_closing: number.trv_{room_name}_valve_closing_degree
```

**Example:**
```yaml
- id: '1761691019774'
  alias: Living room TRV - sync valve with helper
  description: 'Copy the settings from the 0 - 100 helper to the TRV valve position. This will be controlled by a PID controller from Smart thermostat (PID) - see the YAML.'
  use_blueprint:
    path: arnie580/sonoff-trv-pid.yaml
    input:
      thermostat_value: input_number.living_room_trv_valve_position
      max_valve_opening: number.trv_living_room_valve_opening_degree
      max_valve_closing: number.trv_living_room_valve_closing_degree
```

#### 4. External Temperature Sync Automation (automations.yaml)

Create an automation using the `photomoose/sonoff-trvzb-external-temperature-sensor-calibration` blueprint:

```yaml
- id: '{unique_id}'
  alias: Sync {room name} TRV with external sensor
  description: ''
  use_blueprint:
    path: photomoose/sonoff-trvzb-external-temperature-sensor-calibration.yaml
    input:
      external_temperature_sensor: sensor.sensor_{room_name}_temperature
      trv_external_temperature_input:
        - number.trv_{room_name}_external_temperature_input
```

**Example:**
```yaml
- id: '1761512302799'
  alias: Sync living room TRV with external sensor
  description: ''
  use_blueprint:
    path: photomoose/sonoff-trvzb-external-temperature-sensor-calibration.yaml
    input:
      external_temperature_sensor: sensor.sensor_living_room_temperature
      trv_external_temperature_input:
        - number.trv_living_room_external_temperature_input
```

### Current Implementations

This pattern is currently implemented for:

1. **Living room** - Complete setup with all 4 components
2. **Master bedroom** - Complete setup with all 4 components
3. **Bedroom** - Complete setup with all 4 components

### Prerequisites

Before setting up a new room:

1. Ensure the TRV device is paired and available in Home Assistant
2. Ensure an external temperature sensor is available for the room
3. Configure the TRV to use external temperature sensor mode (in Zigbee2MQTT settings)
4. Install the Smart Thermostat (PID) integration from HACS

### PID Tuning

The default PID parameters are:
- **kp**: 60 (Proportional gain)
- **ki**: 0.01 (Integral gain)  
- **kd**: 2000 (Derivative gain)

These can be adjusted per room via the climate entity UI or by modifying the climate.yaml configuration.

### TRV Troubleshooting

- **TRV not responding**: Check that valve sync automation is running
- **Temperature not accurate**: Verify external temperature sensor sync automation is active
- **TRV enters fail-safe mode**: Ensure external temperature sensor reports at least once every 2 hours
