
import asyncio

log.debug("Registering 'Say Hello' automation")


@state_trigger("person.charles")
@state_trigger("person.gaby")
def say_hello( 
    **kwargs
):
    if person.charles == 'home' and person.gaby == 'home':
        person = "Gaby and Charles"
    elif person.charles == 'home':
        person = "Charles"
    else:
        person = "Gaby"

    log.debug(f"Saying hello to {person}")

    if int(state.get(sensor_name)) > 0:
        service.call("light", "turn_on", entity_id=light_name)
    else:
        service.call("light", "turn_off", entity_id=light_name)

