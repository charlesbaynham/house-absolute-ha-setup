"""Quietness, flapping, valve interplay, restart flicker."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, climate_writes, modes, pid, pid_setpoints, policy_packages, set_comfort

ALL = ("living_room", "master_bedroom", "bedroom")
DOOR = "binary_sensor.backdoor_sensor_contact"


class Boot:
    def __init__(self, tmp_path, persons=EVERYONE_HOME, trvs=True, **kw):
        self.cm = house(tmp_path, policy_packages(trvs=trvs), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        return await self.cm.__aexit__(*a)


async def _states_stable(h, seconds, ticks=4):
    """Let the 10 minute reconcile run `ticks` times; return the writes it made."""
    h.watch_calls()
    for _ in range(ticks):
        await h.settle(seconds)
    return [c for c in h._calls if c[0] in ("climate", "input_number", "input_boolean", "input_text")
            and "pid_output" not in str(c[2]) and "valve" not in str(c[2])]


async def test_a_settled_house_makes_no_writes_on_the_reconcile_tick(tmp_path):
    async with Boot(tmp_path) as h:
        await h.settle(60)
        writes = await _states_stable(h, 600)
        assert writes == [], writes


async def test_a_settled_away_house_is_quiet_too(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        await h.set_state(DOOR, "on")
        await h.set_state(DOOR, "off")
        await h.settle(60)
        writes = await _states_stable(h, 600)
        assert writes == [], writes


async def test_rapid_presence_flapping_settles_on_the_last_value(tmp_path):
    async with Boot(tmp_path) as h:
        for i in range(12):
            for who in ("charles", "gaby", "harry"):
                h.person(who, "not_home" if i % 2 == 0 else "home", 5 if i % 2 == 0 else None)
            await h.hass.async_block_till_done()
        # ended on i == 11 -> home
        await h.settle(60)
        assert modes(h) == {r: "heat" for r in ALL}
        assert pid_setpoints(h) == COMFORT
        for who in ("charles", "gaby", "harry"):
            h.person(who, "not_home", 5)
        await h.settle(60)
        assert pid_setpoints(h) == {r: sp - SETBACK for r, sp in COMFORT.items()}


async def test_door_flapping_settles(tmp_path):
    async with Boot(tmp_path) as h:
        for _ in range(8):
            await h.set_state(DOOR, "on")
            await h.set_state(DOOR, "off")
        assert modes(h) == {r: "heat" for r in ALL}
        await h.set_state(DOOR, "on")
        assert set(modes(h).values()) == {"off"}


async def test_all_inputs_at_once(tmp_path):
    """Everything changes in the same instant: door opens, everyone leaves, Charles is away."""
    async with Boot(tmp_path) as h:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        h.hass.states.async_set(DOOR, "on")
        for who in ("charles", "gaby", "harry"):
            h.person(who, "not_home", 5)
        await h.settle(60)
        assert set(modes(h).values()) == {"off"}
        h.hass.states.async_set(DOOR, "off")
        await h.settle(60)
        # Charles is back under 10 km but still not home: master stays off; others setback
        assert modes(h) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}


# --- valves ---------------------------------------------------------------------------------


async def test_valve_helper_follows_the_policy(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.smart_mode_living_room")
        await h.settle(60)
        valve = "input_number.living_room_trv_valve_position"
        assert float(h.state(valve)) > 0, "heating: valve follows the PID output"
        await h.set_state(DOOR, "on")
        assert float(h.state(valve)) == 0.0, "door open: valve closed"
        await h.set_state(DOOR, "off")
        await h.settle(60)
        assert float(h.state(valve)) > 0


# --- restart flicker --------------------------------------------------------------------------


async def test_a_restart_never_flicks_an_off_room_on(tmp_path):
    """The room control blueprint used to set `heat` at every start; every room the policy keeps
    off then blinked on for a moment."""
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm.__aenter__()
    try:
        await set_comfort(a)
        await a.set_person("charles", "not_home", 15)
        await a.settle(11 * 60)
        await a.call("climate", "turn_off", by_hand=True, entity_id=pid("living_room"))
        assert modes(a) == {"living_room": "off", "master_bedroom": "off", "bedroom": "heat"}
        cm2 = house(
            tmp_path, policy_packages(), templates=load_repo_templates(),
            persons={"charles": ("not_home", 15), "gaby": ("home", None), "harry": ("home", None)}, restore_from=a,
        )
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            assert modes(b) == {"living_room": "off", "master_bedroom": "off", "bedroom": "heat"}
            for room in ("living_room", "master_bedroom"):
                assert "heat" not in b.climate_modes_seen(pid(room)), (room, b.climate_modes_seen(pid(room)))
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)


async def test_runs_are_skipped_while_a_presence_fact_has_no_value_but_the_tick_still_acts(tmp_path):
    """At boot the latched sensors have no value until HA has started. A run in that window would
    judge a half-built house (and switch the master bedroom on). Skipped; the 10 min tick still
    treats an unknown fact as 'not away', so a broken sensor cannot freeze the heating."""
    async with Boot(tmp_path) as h:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        assert modes(h)["master_bedroom"] == "off"
        await h.set_state("binary_sensor.charles_away_for_heating", "unknown")
        # something unrelated triggers the policy: must not act on the unknown fact
        await h.call("input_number", "set_value", entity_id="input_number.master_bedroom_comfort_setpoint", value=21.0)
        assert modes(h)["master_bedroom"] == "off"
        # the periodic reconcile does act, treating unknown as "not away"
        await h.settle(11 * 60)
        assert modes(h)["master_bedroom"] == "heat"
