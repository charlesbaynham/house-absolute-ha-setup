"""Occupied switch, boost, turning the heating on by hand, and the back door."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, modes, pid_setpoints, policy_packages, set_comfort, status

ALL = ("living_room", "master_bedroom", "bedroom")
DOOR = "binary_sensor.backdoor_sensor_contact"


class Boot:
    """Async context manager that boots the house with comfort setpoints set."""

    def __init__(self, tmp_path, persons=EVERYONE_HOME, **kw):
        self.cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        return await self.cm.__aexit__(*a)


async def charles_away(h):
    await h.set_person("charles", "not_home", 15)
    await h.settle(11 * 60)
    assert modes(h)["master_bedroom"] == "off"


# --- occupied ----------------------------------------------------------------------------


async def test_occupied_keeps_master_bedroom_heated_while_charles_is_away(tmp_path):
    async with Boot(tmp_path) as h:
        await charles_away(h)
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.master_bedroom_occupied")
        assert modes(h)["master_bedroom"] == "heat"
        assert pid_setpoints(h)["master_bedroom"] == COMFORT["master_bedroom"]
        assert status(h, "master_bedroom").startswith("comfort - room occupied")
        await h.call("input_boolean", "turn_off", entity_id="input_boolean.master_bedroom_occupied")
        assert modes(h)["master_bedroom"] == "off"


async def test_occupied_clears_when_charles_gets_home(tmp_path):
    async with Boot(tmp_path) as h:
        await charles_away(h)
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.master_bedroom_occupied")
        await h.set_person("charles", "home")
        assert h.state("input_boolean.master_bedroom_occupied") == "off"
        assert modes(h)["master_bedroom"] == "heat"
        # next trip starts clean
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        assert modes(h)["master_bedroom"] == "off"


async def test_occupied_beats_setback_and_far_away_but_only_for_that_room(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.bedroom_occupied")
        assert pid_setpoints(h)["bedroom"] == COMFORT["bedroom"], "occupied: no setback"
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"] - SETBACK
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        assert modes(h) == {"living_room": "off", "master_bedroom": "off", "bedroom": "heat"}
        assert pid_setpoints(h)["bedroom"] == COMFORT["bedroom"]


async def test_occupied_does_not_survive_into_a_normal_day_for_other_rooms(tmp_path):
    """Only the room whose switch is on is affected."""
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.living_room_occupied")
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"]
        assert pid_setpoints(h)["master_bedroom"] == COMFORT["master_bedroom"] - SETBACK


# --- boost ---------------------------------------------------------------------------------


async def test_boost_heats_a_room_that_is_off_and_hands_back_after(tmp_path):
    async with Boot(tmp_path) as h:
        await charles_away(h)
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.boost_mode_master_bedroom")
        assert modes(h)["master_bedroom"] == "heat"
        assert float(h.state("input_number.master_bedroom_trv_valve_position")) == 100.0
        await h.call("input_boolean", "turn_off", entity_id="input_boolean.boost_mode_master_bedroom")
        assert modes(h)["master_bedroom"] == "off"
        assert float(h.state("input_number.master_bedroom_trv_valve_position")) == 0.0


# --- by hand ---------------------------------------------------------------------------------


async def test_turning_heat_on_by_hand_against_person_follow_marks_the_room_occupied(tmp_path):
    async with Boot(tmp_path) as h:
        await charles_away(h)
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id="climate.master_bedroom_trv_pid_controller", hvac_mode="heat")
        assert h.state("input_boolean.master_bedroom_occupied") == "on"
        assert modes(h)["master_bedroom"] == "heat"


async def test_turning_heat_on_by_hand_against_far_away_marks_the_room_occupied(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_person("harry", "not_home", 5)
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        assert set(modes(h).values()) == {"off"}
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id="climate.bedroom_trv_pid_controller", hvac_mode="heat")
        assert h.state("input_boolean.bedroom_occupied") == "on"
        assert modes(h) == {"living_room": "off", "master_bedroom": "off", "bedroom": "heat"}


async def test_an_automation_switching_heat_on_against_the_policy_is_reverted(tmp_path):
    async with Boot(tmp_path) as h:
        await charles_away(h)
        await h.call("climate", "set_hvac_mode", entity_id="climate.master_bedroom_trv_pid_controller", hvac_mode="heat")
        assert modes(h)["master_bedroom"] == "off"
        assert h.state("input_boolean.master_bedroom_occupied") == "off"


async def test_by_hand_heat_against_the_back_door_is_reverted(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_state(DOOR, "on")
        assert set(modes(h).values()) == {"off"}
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id="climate.living_room_trv_pid_controller", hvac_mode="heat")
        assert modes(h)["living_room"] == "off"
        assert h.state("input_boolean.living_room_occupied") == "off"


# --- back door -----------------------------------------------------------------------------


async def test_back_door_open_switches_everything_off_and_closing_restores(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_state(DOOR, "on")
        assert set(modes(h).values()) == {"off"}
        assert status(h, "bedroom").startswith("off - back door open")
        await h.set_state(DOOR, "off")
        assert set(modes(h).values()) == {"heat"}
        assert pid_setpoints(h) == COMFORT


async def test_back_door_beats_occupied(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.living_room_occupied")
        await h.set_state(DOOR, "on")
        assert modes(h)["living_room"] == "off"
        await h.set_state(DOOR, "off")
        assert modes(h)["living_room"] == "heat"


async def test_closing_the_door_returns_each_room_to_its_own_mode_not_a_saved_list(tmp_path):
    async with Boot(tmp_path) as h:
        await h.set_state(DOOR, "on")
        # While the door is open the household leaves and Charles goes away
        for who in ("gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        await h.set_state(DOOR, "off")
        assert modes(h) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"] - SETBACK


async def test_door_open_through_far_away_stays_off_after_closing(tmp_path):
    """The old back door pause turned every room it had saved back ON when the door closed, even
    if far-away mode had switched them off meanwhile."""
    async with Boot(tmp_path) as h:
        await h.set_state(DOOR, "on")
        await h.set_person("harry", "not_home", 5)
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        await h.set_state(DOOR, "off")
        assert set(modes(h).values()) == {"off"}
