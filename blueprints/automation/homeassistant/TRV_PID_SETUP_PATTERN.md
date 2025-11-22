# TRV PID Controller Setup Pattern

This document describes the standardized pattern for setting up a TRV (Thermostatic Radiator Valve) with PID control in a room.

## Overview

Each room with TRV PID control requires the following components:

1. **Input Number Helper** - Stores valve position (0-100) controlled by PID
2. **Climate Entity** - Smart thermostat with PID controller
3. **Valve Sync Automation** - Syncs PID output to TRV valve position
4. **External Temperature Sync Automation** - Syncs external sensor to TRV

## Complete Setup Template

### 1. Input Number Helper (configuration.yaml)

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

### 2. Climate Entity (climate.yaml)

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

### 3. Valve Position Sync Automation (automations.yaml)

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

### 4. External Temperature Sync Automation (automations.yaml)

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

## Current Implementations

This pattern is currently implemented for:

1. **Living room** - Complete setup with all 4 components
2. **Master bedroom** - Complete setup with all 4 components
3. **Bedroom** - Complete setup with all 4 components

## Prerequisites

Before setting up a new room:

1. Ensure the TRV device is paired and available in Home Assistant
2. Ensure an external temperature sensor is available for the room
3. Configure the TRV to use external temperature sensor mode (in Zigbee2MQTT settings)
4. Install the Smart Thermostat (PID) integration from HACS

## PID Tuning

The default PID parameters are:
- **kp**: 60 (Proportional gain)
- **ki**: 0.01 (Integral gain)  
- **kd**: 2000 (Derivative gain)

These can be adjusted per room via the climate entity UI or by modifying the climate.yaml configuration.

## Troubleshooting

- **TRV not responding**: Check that valve sync automation is running
- **Temperature not accurate**: Verify external temperature sensor sync automation is active
- **TRV enters fail-safe mode**: Ensure external temperature sensor reports at least once every 2 hours
