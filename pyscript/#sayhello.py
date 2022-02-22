
import asyncio

log.debug("Registering 'Say Hello' automation")

DELAY_S = 5 * 60

@state_trigger("group.any_home=='home'", state_hold=DELAY_S)
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

    message = f"Hello {person}, welcome home"
    service.call("tts", "google_translate_say", entity_id="media_player.living_room_speaker", message=message)
    # service.call("notify", "mobile_app_charles_honor", message=message)
