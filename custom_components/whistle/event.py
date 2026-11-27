from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from . import Heard, WhistleConfigEntry
from .const import DOMAIN
from .dedup import Verdict


async def async_setup_entry(hass: HomeAssistant, entry: WhistleConfigEntry, add: AddEntitiesCallback) -> None:
    store = Store[list[str]](hass, 1, f"{DOMAIN}.event_types")
    add([HouseWhistle(entry, store, await store.async_load() or [])])


class HouseWhistle(EventEntity):
    """One event per whistle, however many nodes heard it."""

    _attr_has_entity_name = False
    _attr_name = "Whistle"
    _attr_icon = "mdi:whistle"

    def __init__(self, entry: WhistleConfigEntry, store: Store[list[str]], event_types: list[str]):
        self.hub = entry.runtime_data
        self.store = store
        self._attr_unique_id = f"{entry.entry_id}_whistle"
        self._attr_event_types = event_types
        self.entity_id = "event.whistle"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.hub.listeners.append(self._on_verdict)
        self.async_on_remove(lambda: self.hub.listeners.remove(self._on_verdict))

    @callback
    def _on_verdict(self, verdict: Verdict, heard: list[Heard]) -> None:
        if verdict.event_type not in self._attr_event_types:
            # HA refuses events whose type isn't declared; new labels appear as the server learns them.
            self._attr_event_types = [*self._attr_event_types, verdict.event_type]
            self.store.async_delay_save(lambda: self._attr_event_types, 1)
        top = heard[0]
        self._trigger_event(
            verdict.event_type,
            {
                "room": top.room,
                "area_id": top.area_id,
                "room_confident": verdict.confident,
                "node": top.node,
                "level": top.level,
                "score": top.score,
                "heard_by": [vars(h) for h in heard],
            },
        )
        self.async_write_ha_state()
        self.hass.async_create_task(self.hub.async_feedback(verdict, self.entity_id, self._attr_event_types))
