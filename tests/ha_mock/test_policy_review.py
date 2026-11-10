"""Regressions found by an independent review of the policy (2026-11-10)."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, modes, pid, pid_setpoints, policy_packages, set_comfort, status, trv

LR = "living_room"
MB = "master_bedroom"


class Boot:
    def __init__(self, tmp_path, persons=EVERYONE_HOME, trvs=False, **kw):
        self.cm = house(tmp_path, policy_packages(trvs=trvs), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        return await self.cm.__aexit__(*a)


def comfort(h, room):
    return float(h.state(f"input_number.{room}_comfort_setpoint"))


async def test_harry_home_alone_while_charles_and_gaby_are_far_gets_heating(tmp_path):
    """'House far away' only looks at Charles and Gaby; it must not switch off a house someone is in."""
    async with Boot(tmp_path) as h:
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        assert h.state("binary_sensor.anyone_home") == "on"
        assert h.state("binary_sensor.house_far_away") == "off"
        assert modes(h) == {LR: "heat", MB: "off", "bedroom": "heat"}  # master follows Charles
        assert pid_setpoints(h)[LR] == COMFORT[LR]


async def test_harry_arriving_during_a_far_away_trip_brings_the_heating_back(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_person("harry", "not_home", 5)
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        assert modes(h)[LR] == "off"
        await h.set_person("harry", "home")
        assert modes(h)[LR] == "heat"
        assert pid_setpoints(h)[LR] == COMFORT[LR]


async def test_occupied_in_a_room_that_follows_nobody_clears_when_someone_gets_home(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id=pid(LR), hvac_mode="heat")
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.living_room_occupied")
        assert pid_setpoints(h)[LR] == COMFORT[LR], "occupied: no setback"
        await h.set_person("gaby", "home")
        assert h.state("input_boolean.living_room_occupied") == "off"
        # and the next trip starts clean
        await h.set_person("gaby", "not_home", 5)
        assert pid_setpoints(h)[LR] == COMFORT[LR] - SETBACK


async def test_edit_while_off_and_nobody_home_is_read_as_typed(tmp_path):
    """An off room holds the comfort setpoint, so a later edit is never 'reduced by the offset'."""
    async with Boot(tmp_path, trvs=True) as h:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        assert modes(h)[MB] == "off"
        for who in ("gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert h.attr(pid(MB), "temperature") == COMFORT[MB], "off rooms hold comfort, not the setback value"
        await h.call("climate", "set_temperature", entity_id=trv(MB), temperature=20.0)
        assert comfort(h, MB) == 20.0


async def test_off_rooms_keep_comfort_through_setback_and_a_person_leaving(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert pid_setpoints(h)[MB] == COMFORT[MB] - SETBACK
        await h.set_person("charles", "not_home", 15)  # now confirmed away
        await h.settle(11 * 60)
        assert modes(h)[MB] == "off"
        assert pid_setpoints(h)[MB] == COMFORT[MB], "off: shows comfort, not a stale setback value"
        assert comfort(h, MB) == COMFORT[MB]
        await h.set_person("charles", "home")
        assert pid_setpoints(h)[MB] == COMFORT[MB], "Charles is home: comfort, and nothing was lost on the way"


async def test_one_press_is_enough_when_the_room_is_switched_off_and_the_person_is_away(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        # (already off because Charles is away) the room is also switched off from the dashboard
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.master_bedroom_heating_disabled")
        assert modes(h)[MB] == "off"
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id=pid(MB), hvac_mode="heat")
        assert modes(h)[MB] == "heat"
        assert h.state("input_boolean.master_bedroom_heating_disabled") == "off"
        assert h.state("input_boolean.master_bedroom_occupied") == "on"


async def test_the_policy_does_not_run_on_every_sensor_report(tmp_path):
    """The PID's current_temperature attribute changes with every sensor report; the policy only
    cares about its state and its setpoint."""
    from .harness import set_room_temp

    async with Boot(tmp_path) as h:
        await h.settle(60)
        runs = []
        h.hass.bus.async_listen(
            "automation_triggered",
            lambda e: runs.append(e.data["entity_id"]) if e.data["entity_id"] == "automation.living_room_heating_policy" else None,
        )
        for i in range(20):
            set_room_temp(h.hass, LR, 19.0 + i * 0.1)
            await h.hass.async_block_till_done()
        assert len(runs) <= 2, len(runs)
