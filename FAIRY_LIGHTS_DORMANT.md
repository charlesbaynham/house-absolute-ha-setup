# Fairy lights — dormant

The living room fairy lights socket (Tasmota `LocalBytes PM`, MAC `14:08:08:69:52:69`) was
repurposed as the **master bedroom fan** on 2026-07-26. Nothing was deleted: everything the
fairy lights used is preserved in an inert state and can be brought back once a replacement
socket is bought.

## What the fairy lights actually did

There were **no fairy-lights-specific automations**. The socket was driven entirely by:

1. **Living Room area membership** — six `light.turn_on` / `light.turn_off` actions in
   `packages/living_room_lights.yaml` (wall button, cosy button hold, cosy cycle "off" step,
   presence restore, presence timeout) and one in `scripts.yaml` (`script.police_mode`) target
   `area_id: living_room`. Any light in that area is picked up automatically.
2. **One explicit scene reference** — scene `1767728852849` ("Living room cosy brighter") set
   `light.fairy_lights_fairy_lights` to `on`.

That is the complete set. Because the area targeting is membership-based rather than
entity-based, a replacement socket placed in the Living Room area is picked up by all six
actions with no config changes at all.

## What is preserved, and where

| Asset | State | Location |
|---|---|---|
| `switch_as_x` helper "Fairy lights" (switch → light) | Config entry `01KMRBSKG6XGC0RKBGZNPB5VKX`, **disabled** (`disabled_by: user`) | Entity registry / config entries |
| `light.fairy_lights_fairy_lights` | Registry row retained, `disabled_by: config_entry` — this **reserves the entity ID** so it can be reused verbatim | Entity registry |
| Scene membership | Commented out, ready to uncomment | `scenes.yaml`, scene `1767728852849` |

The disabled `switch_as_x` entry still stores `entity_id: switch.tasmota_fairy_lights`, which no
longer exists — that switch was renamed to `switch.master_bedroom_fan_socket`. This is
deliberate: re-enabling the old entry **cannot** hijack the bedroom fan. `switch_as_x` does not
support reconfiguration, so the entry must be deleted and recreated against the new socket.

## Restoring the fairy lights

1. Flash / adopt the replacement socket in Tasmota and let it appear in Home Assistant.
2. Assign its device to the **Living Room** area and name the device `Fairy lights`.
3. Delete the disabled `switch_as_x` config entry `01KMRBSKG6XGC0RKBGZNPB5VKX`
   (*Settings → Devices & Services → Switch as X → "Fairy lights" → Delete*). This also frees
   the reserved `light.fairy_lights_fairy_lights` entity ID.
4. Create a new *Switch as X* helper: source = the new socket's `switch.*` entity,
   target domain = `light`, title `Fairy lights`. Then rename the resulting entity to
   `light.fairy_lights_fairy_lights` so the scene reference below matches.
5. Uncomment the `light.fairy_lights_fairy_lights` block in `scenes.yaml` (scene
   `1767728852849`, "Living room cosy brighter") and reload scenes
   (*Developer Tools → YAML → Scenes*), or restart Home Assistant.
6. Verify: activate `scene.living_room_cosy_brighter` and press the living room wall button —
   the fairy lights should follow both.

## The socket in its new role

| Item | Value |
|---|---|
| Device | `Master bedroom fan`, area **Master bedroom** |
| Primary entity | `fan.master_bedroom_fan` (`switch_as_x`, target domain `fan`) |
| Underlying relay | `switch.master_bedroom_fan_socket` (hidden by the wrapper) |
| Power / energy sensors | `sensor.master_bedroom_fan_power`, `…_energy_today`, `…_energy_total`, etc. |

It is exposed as a `fan` rather than a `light` on purpose: the master bedroom's
`light.turn_off` area actions (e.g. "Turn off all lights when everyone leaves" in
`automations.yaml`) target the `light` domain, so the fan is not swept off with the lights.
