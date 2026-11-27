"""House-wide whistle events from the nodes' MQTT detections: dedup across rooms, room = loudest node's Area."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass

from homeassistant.components import mqtt
from homeassistant.components.automation import DATA_COMPONENT as AUTOMATIONS
from homeassistant.components.automation import automations_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_COLLECT_S,
    CONF_CONFIDENT_DB,
    CONF_MATCH_S,
    CONF_MAX_AGE_S,
    DEFAULTS,
    IGNORED_TYPES,
    SCHEMA,
    TOPIC_DETECTION,
    TOPIC_STATUS,
    device_identifier,
    node_of,
)
from .dedup import Detection, Group, Grouper, Verdict

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.EVENT]

type WhistleConfigEntry = ConfigEntry[WhistleHub]


@dataclass(frozen=True)
class Heard:
    node: str
    room: str | None
    area_id: str | None
    level: float
    score: float | None


class WhistleHub:
    def __init__(self, hass: HomeAssistant, entry: WhistleConfigEntry):
        self.hass = hass
        self.opt = {**DEFAULTS, **entry.options}
        self.grouper = Grouper(self.opt[CONF_MATCH_S], self.opt[CONF_COLLECT_S], self.opt[CONF_CONFIDENT_DB])
        self.online: set[str] = set()
        self.seen: deque[tuple[str, str]] = deque(maxlen=256)
        self.listeners: list = []  # callables taking (Verdict, list[Heard])

    async def async_start(self, entry: WhistleConfigEntry) -> None:
        for topic, cb in ((TOPIC_STATUS, self._on_status), (TOPIC_DETECTION, self._on_detection)):
            entry.async_on_unload(await mqtt.async_subscribe(self.hass, topic, cb, qos=1))

    @callback
    def _on_status(self, msg: mqtt.ReceiveMessage) -> None:
        node = node_of(msg.topic)
        if msg.payload == "online":
            self.online.add(node)
        else:
            self.online.discard(node)

    @callback
    def _on_detection(self, msg: mqtt.ReceiveMessage) -> None:
        node = node_of(msg.topic)
        try:
            p = json.loads(msg.payload)
            if p.get("v") != SCHEMA:
                raise ValueError(f"schema {p.get('v')}")
            d = Detection(node, str(p["event_type"]), str(p["id"]), float(p.get("t") or 0), time.monotonic(),
                          float(p.get("level") or 0), p)
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.warning("whistle/%s: bad detection %r: %s", node, msg.payload, e)
            return
        if d.event_type in IGNORED_TYPES or (node, d.id) in self.seen:
            return
        self.seen.append((node, d.id))
        if d.t and abs(time.time() - d.t) > self.opt[CONF_MAX_AGE_S]:
            _LOGGER.info("whistle/%s: dropping stale %s (%.1f s old)", node, d.event_type, time.time() - d.t)
            return
        group, new = self.grouper.add(d)
        if new:
            async_call_later(self.hass, self.opt[CONF_COLLECT_S], callback(lambda _: self._close(group)))
        if self.online and self.online <= group.nodes:
            self._close(group)  # everyone who could hear it has spoken

    @callback
    def _close(self, group: Group) -> None:
        if verdict := self.grouper.close(group):
            heard = [self._heard(d) for d in verdict.ranked]
            for listener in self.listeners:
                listener(verdict, heard)

    def _heard(self, d: Detection) -> Heard:
        device = dr.async_get(self.hass).async_get_device(identifiers={device_identifier(d.node)})
        area = ar.async_get(self.hass).async_get_area(device.area_id) if device and device.area_id else None
        return Heard(d.node, area.name if area else None, area.id if area else None, d.level, d.payload.get("score"))

    def handled(self, event_type: str, entity_id: str, known_types: list[str]) -> bool:
        """Whether an enabled automation on `entity_id` acts on `event_type`: one that names it, or one that
        names no known pattern at all (a catch-all). A guess from the config text, not an evaluation."""
        for eid in automations_with_entity(self.hass, entity_id):
            automation = self.hass.data[AUTOMATIONS].get_entity(eid)
            if automation is None or self.hass.states.is_state(eid, "off"):
                continue
            text = json.dumps(automation.raw_config or {}, default=str)
            named = {t for t in known_types if re.search(rf"\b{re.escape(t)}\b", text)}
            if event_type in named or not named:
                return True
        return False

    async def async_feedback(self, verdict: Verdict, entity_id: str, known_types: list[str]) -> None:
        result = "ok" if self.handled(verdict.event_type, entity_id, known_types) else "no_action"
        for i, d in enumerate(verdict.ranked):
            payload = json.dumps({"v": SCHEMA, "id": d.id, "result": result if i == 0 else "dup"}, separators=(",", ":"))
            await mqtt.async_publish(self.hass, f"whistle/{d.node}/feedback", payload, qos=1)


async def async_setup_entry(hass: HomeAssistant, entry: WhistleConfigEntry) -> bool:
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT is not available")
    entry.runtime_data = WhistleHub(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await entry.runtime_data.async_start(entry)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: WhistleConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WhistleConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
