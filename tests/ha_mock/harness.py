"""Mock house: a real Home Assistant core running this repo's own YAML.

Nothing here re-implements repo logic. It loads the real packages, blueprints and the real
`smart_thermostat` custom component into a real HA core (the version pinned in the test venv,
which should match production), and replaces only what cannot exist off the box: people/phones
(states are set directly), the Zigbee TRV/valve hardware (stubs), and the temperature sensors.

Run:  uv venv --python 3.14 venv && uv pip install --python venv/bin/python \
        homeassistant==2026.10.0 pytest-homeassistant-custom-component
      venv/bin/pytest tests/ha_mock
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

from homeassistant.config import merge_packages_config
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

REPO = Path(__file__).resolve().parents[2]

ROOMS = ("living_room", "master_bedroom", "bedroom")

# Home coordinates used by the mock (any point works, the maths is relative).
HOME = (51.4963, -0.1308)


def km_north(km: float) -> tuple[float, float]:
    """A point `km` north of home (1 degree of latitude ~ 111.19 km)."""
    return (HOME[0] + km / 111.19, HOME[1])


def prepare_config_dir(tmp: Path) -> Path:
    """A throwaway config dir pointing at the repo's blueprints and the real PID component."""
    cfg = tmp / "config"
    (cfg / "custom_components").mkdir(parents=True)
    os.symlink(REPO / "blueprints", cfg / "blueprints")
    os.symlink(
        REPO / "custom_components" / "smart_thermostat",
        cfg / "custom_components" / "smart_thermostat",
    )
    return cfg


def _drop_hardware_automations(pkg: dict) -> dict:
    """Per-room packages: stub the automations that only talk to Zigbee hardware.

    The valve-sync automation keeps its alias (so its entity id exists: the room control
    blueprint turns it on) but does nothing; the external-temperature sync and the
    hot-while-closed watchdog are dropped. The legacy template `button` platform is not
    supported by HA 2026.10 (it does not exist on the live box either).
    """
    pkg = copy.deepcopy(pkg)
    pkg.pop("button", None)
    kept = []
    for auto in pkg.get("automation", []):
        bp = (auto.get("use_blueprint") or {}).get("path", "")
        if bp.startswith("arnie580/"):
            kept.append(
                {
                    "id": auto["id"],
                    "alias": auto["alias"],
                    "triggers": [{"trigger": "event", "event_type": "mock_never"}],
                    "actions": [],
                }
            )
        elif bp.startswith("photomoose/") or "watchdog" in bp:
            continue
        else:
            kept.append(auto)
    pkg["automation"] = kept
    return pkg


def load_repo_packages(names: list[str], overrides: dict[str, dict] | None = None) -> dict:
    """Load `packages/<name>.yaml` for each name (per-room packages get hardware stubbed)."""
    packages = {}
    for name in names:
        pkg = load_yaml(str(REPO / "packages" / f"{name}.yaml"))
        if name.startswith("climate_") and name.replace("climate_", "") in ROOMS:
            pkg = _drop_hardware_automations(pkg)
        packages[name] = pkg
    for name, pkg in (overrides or {}).items():
        packages[name] = pkg
    return packages


def load_repo_templates() -> list:
    """The `template:` list from the root template_sensors.yaml (anyone_home etc.)."""
    return load_yaml(str(REPO / "template_sensors.yaml"))


async def setup_house(hass, packages: dict, *, templates: list | None = None) -> dict:
    """Merge `packages` like HA does at boot and set every domain up."""
    base: dict = {"homeassistant": {}}
    if templates:
        base["template"] = templates
    merged = await merge_packages_config(hass, base, packages)
    await async_setup_component(hass, "zone", {})
    # Entities others depend on first, then the rest, automations last.
    order = [d for d in merged if d not in ("homeassistant", "automation", "template")]
    for domain in order:
        assert await async_setup_component(hass, domain, merged), f"setup of {domain} failed"
    if "template" in merged:
        assert await async_setup_component(hass, "template", merged)
    if "automation" in merged:
        assert await async_setup_component(hass, "automation", merged)
    await hass.async_block_till_done()
    return merged


# --- the outside world ----------------------------------------------------------------------


def set_person(hass, who: str, state: str, km_from_home: float | None = None) -> None:
    attrs = {"friendly_name": who.capitalize()}
    if km_from_home is not None:
        lat, lon = km_north(km_from_home)
        attrs.update(latitude=lat, longitude=lon)
    elif state == "home":
        attrs.update(latitude=HOME[0], longitude=HOME[1])
    hass.states.async_set(f"person.{who}", state, attrs)


def set_room_temp(hass, room: str, value: float) -> None:
    hass.states.async_set(
        f"sensor.sensor_{room}_temperature",
        str(value),
        {"unit_of_measurement": "°C", "device_class": "temperature"},
    )


# --- running houses, restarts ---------------------------------------------------------------

import asyncio
import contextlib
import importlib
import json
import sys
from datetime import timedelta

from homeassistant import loader
from homeassistant.helpers import restore_state
from homeassistant.helpers.json import json_bytes
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Context, CoreState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_test_home_assistant,
    mock_restore_cache,
)

# The live box's disabled automations (UI-disabled, restored as `off` across restarts).
BOOT_SETTLE_S = 60
LIVE_DISABLED = ["automation.master_bedroom_restart_heating_at_4am"]


CLOCK = None  # set by the autouse `clock` fixture in conftest.py (pytest-freezer)


def tick(seconds: float) -> None:
    CLOCK.tick(timedelta(seconds=seconds))


async def _yield_loop(n: int = 20) -> None:
    for _ in range(n):
        await asyncio.sleep(0)


class House:
    """One running mock house. `restart()` returns a fresh house primed with this one's states
    as restore data, which is what HA does across a real restart."""

    def __init__(self, hass, tmp: Path, packages: dict, templates, persons, temps, calls=None):
        self.hass = hass
        self.tmp = tmp
        self.packages = packages
        self.templates = templates
        self.persons = persons
        self.temps = temps
        self._calls: list = calls if calls is not None else []
        self._user = None

    # state helpers ----------------------------------------------------------------------
    def state(self, entity_id: str) -> str:
        return self.hass.states.get(entity_id).state

    def attr(self, entity_id: str, name: str):
        return self.hass.states.get(entity_id).attributes.get(name)

    async def settle(self, seconds: float = 0.0) -> None:
        """Advance the (frozen, cumulative) mock clock by `seconds`, fire due timers and
        `delay`s, then wait for the queued automation runs. Time only moves through here, so
        `for:` debounces and delays behave exactly as in production. (`async_block_till_done`
        alone would wait in real time for an automation sitting in a `delay`.)"""
        await _yield_loop()
        if seconds:
            tick(seconds)
            async_fire_time_changed(self.hass)
            await _yield_loop()
        await self.hass.async_block_till_done()

    async def call(self, domain, service, *, by_hand: bool = False, **data):
        """Call a service. `by_hand=True` gives it a user context, like the dashboard, the app or
        a REST call with a token; without it the call looks like an automation's."""
        if by_hand and self._user is None:
            self._user = await self.hass.auth.async_create_user("Charles", group_ids=["system-admin"])
        ctx = Context(user_id=self._user.id) if by_hand else Context()
        await self.hass.services.async_call(domain, service, data, blocking=True, context=ctx)
        await self.hass.async_block_till_done()

    def service_calls(self, domain: str) -> list:
        """Every `<domain>.*` service call seen since `watch_calls()`."""
        return [c for c in self._calls if c[0] == domain]

    def climate_modes_seen(self, entity_id: str) -> list:
        """Every distinct hvac state the climate entity went through since boot, in order."""
        seen: list = []
        for eid, st, _ in self.history:
            if eid == entity_id and (not seen or seen[-1] != st):
                seen.append(st)
        return seen

    def watch_calls(self) -> None:
        """Forget the calls so far (everything since boot is kept until you do)."""
        self._calls.clear()

    def person(self, who, state, km=None):
        set_person(self.hass, who, state, km)

    async def set_person(self, who, state, km=None):
        set_person(self.hass, who, state, km)
        await self.hass.async_block_till_done()

    async def set_state(self, entity_id, state, **attrs):
        self.hass.states.async_set(entity_id, state, attrs)
        await self.hass.async_block_till_done()


@contextlib.asynccontextmanager
async def house(
    tmp: Path,
    packages: dict,
    *,
    templates: list | None = None,
    persons: dict | None = None,
    restore_from: House | None = None,
    live_disabled: bool = True,
    extra_states: dict | None = None,
    restore_filter=None,
):
    """Boot a mock house. `persons` maps name -> (state, km_from_home)."""
    persons = persons or {}
    cfg = prepare_config_dir(tmp / f"cfg{len(list(tmp.glob('cfg*')))}")
    async with async_test_home_assistant() as hass:
        hass.config.config_dir = str(cfg)
        hass.config.latitude, hass.config.longitude = HOME
        for name in [m for m in sys.modules if m == "custom_components" or m.startswith("custom_components.")]:
            del sys.modules[name]
        sys.path.insert(0, str(cfg.parent / "config"))
        sys.path[:] = [p for p in sys.path if p != str(cfg.parent / "config")]
        sys.path.insert(0, str(cfg))
        importlib.invalidate_caches()
        hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)

        if restore_from is not None:
            # What a real shutdown writes and the next boot reads: states AND the extra stored
            # data some entities (trigger-based templates, ...) restore from.
            stored = restore_state.async_get(restore_from.hass).async_get_stored_states()
            data = restore_state.RestoreStateData(hass)
            # Through JSON, like the real Store write + read, so datetimes become strings etc.
            dumped = json.loads(json_bytes([st.as_dict() for st in stored]))
            data.last_states = {
                d["state"]["entity_id"]: restore_state.StoredState.from_dict(d)
                for d in dumped
                if restore_filter is None or restore_filter(d["state"]["entity_id"])
            }
            hass.data[restore_state.DATA_RESTORE_STATE] = data
        for who, (st, km) in persons.items():
            set_person(hass, who, st, km)
        for room in ROOMS:
            set_room_temp(hass, room, 20.0)
        # Hardware that lives outside HA's own config: the back door contact starts closed
        hass.states.async_set("binary_sensor.backdoor_sensor_contact", "off")
        for ent, (st, attrs) in (extra_states or {}).items():
            hass.states.async_set(ent, st, attrs)

        calls: list = []

        def _record(event):
            d = event.data
            calls.append((d["domain"], d["service"], dict(d.get("service_data", {}))))

        hass.bus.async_listen("call_service", _record)

        history: list = []

        def _hist(event):
            eid = event.data["entity_id"]
            if eid.startswith("climate."):
                new = event.data.get("new_state")
                history.append((eid, new.state if new else None, new.attributes.get("temperature") if new else None))

        hass.bus.async_listen("state_changed", _hist)

        hass.set_state(CoreState.starting)  # like HA's own boot: start-triggers fire on setup
        await setup_house(hass, packages, templates=templates)
        hass.set_state(CoreState.running)
        # What HA does at the end of boot; `homeassistant: start` triggers listen for STARTED.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await _yield_loop()
        # Run out the start-up delays (e.g. the away-mode machine's 30 s re-assert)
        tick(BOOT_SETTLE_S)
        async_fire_time_changed(hass)
        await _yield_loop()
        await hass.async_block_till_done()
        h = House(hass, tmp, packages, templates, persons, None, calls)
        h.history = history
        if live_disabled and restore_from is None:
            for ent in LIVE_DISABLED:
                if hass.states.get(ent):
                    await h.call("automation", "turn_off", entity_id=ent)
        try:
            yield h
        finally:
            await hass.async_stop(force=True)
            if str(cfg) in sys.path:
                sys.path.remove(str(cfg))


def trv_stubs() -> dict:
    """Stand-ins for the physical Sonoff TRVs, `climate.trv_<room>` (the room control blueprint
    mirrors their setpoint with the PID). A generic thermostat on a dummy heater is enough:
    it has a settable target temperature, which is all the mirror needs."""
    pkg: dict = {"climate": [], "input_boolean": {}}
    for room in ROOMS:
        pkg["input_boolean"][f"trv_stub_heater_{room}"] = {}
        pkg["climate"].append(
            {
                "platform": "generic_thermostat",
                "name": "TRV " + room.replace("_", " ").capitalize(),
                "heater": f"input_boolean.trv_stub_heater_{room}",
                "target_sensor": f"sensor.sensor_{room}_temperature",
                "min_temp": 5,
                "max_temp": 30,
            }
        )
    return pkg
