log.info("Setting up light replay monitors")

# Get all the replay sensors
replay_sensors = [f for f in state.names() if 'replay' in f]

# We expect that for each sensor named e.g. "sensor.replay_light_bedroom_1"
# there's a light named "light.bedroom_1".
# Confirm this:
replay_sensors_to_light = {}
for sensor in replay_sensors:
    light_name = "light." + sensor[20:]
    log.debug(f"{sensor} => {light_name}")
    try:
        light = state.get(light_name)
    except NameError:
        log.warning(f"{sensor} => {light_name} mapping not found")
        continue
    replay_sensors_to_light[sensor] = light_name

log.info(f"replay_sensors_to_light: {replay_sensors_to_light}")

# For each replay sensor + light combo, build a function which copies
# the state of the replay sensor to its light but only if away mode is active.
# Trigger it by the replay sensor's state
for sensor_name, light_name in replay_sensors_to_light.items():
    @state_active("input_boolean.away_mode_active == 'on'")
    @state_trigger(sensor_name)
    def trigger_replay_func(**kwargs):
        log.debug(f"trigger_replay_func for {sensor_name} called with kwargs={kwargs}")

        if int(state.get(sensor_name)) > 0:
            service.call("light", "turn_on", entity_id=light_name)
        else:
            service.call("light", "turn_off", entity_id=light_name)

    globals()["trigger_replay_" + light_name] = trigger_replay_func
