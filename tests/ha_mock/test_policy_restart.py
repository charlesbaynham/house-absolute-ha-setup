"""Restarts. The old design lost its state here (and a blueprint turned heat back on at start)."""

import pytest

from .harness import ROOMS, house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, modes, pid_setpoints, policy_packages, set_comfort, status

DOOR = "binary_sensor.backdoor_sensor_contact"
LEAVE = {"charles": ("not_home", 5), "gaby": ("not_home", 5), "harry": ("not_home", 5)}


def snap(h):
    return {
        "modes": modes(h),
        "setpoints": pid_setpoints(h),
        "comfort": {r: float(h.state(f"input_number.{r}_comfort_setpoint")) for r in ROOMS},
        "last_written": {r: float(h.state(f"input_number.{r}_policy_last_setpoint")) for r in ROOMS},
        "status": {r: status(h, r) for r in ROOMS},
        "far": h.state("binary_sensor.house_far_away"),
        "charles": h.state("binary_sensor.charles_away_for_heating"),
        "occupied": {r: h.state(f"input_boolean.{r}_occupied") for r in ROOMS},
    }


async def a_house(tmp_path, **kw):
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME, **kw)
    h = await cm.__aenter__()
    await set_comfort(h)
    return cm, h


async def restart(tmp_path, a, persons, **kw):
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons, restore_from=a, **kw)
    return cm, await cm.__aenter__()


# --- unchanged world: the restart must change nothing ---------------------------------------


async def _charles_away(h):
    await h.set_person("charles", "not_home", 15)
    await h.settle(11 * 60)


async def _nobody_home(h):
    for who in ("charles", "gaby", "harry"):
        await h.set_person(who, "not_home", 5)


async def _far_away(h):
    await h.set_person("harry", "not_home", 5)
    await h.set_person("charles", "not_home", 80)
    await h.set_person("gaby", "not_home", 80)
    await h.settle(31 * 60)


async def _door_open(h):
    await h.set_state(DOOR, "on")


async def _occupied_while_charles_away(h):
    await _charles_away(h)
    await h.call("input_boolean", "turn_on", entity_id="input_boolean.master_bedroom_occupied")


async def _everything(h):
    await _nobody_home(h)
    await h.set_person("charles", "not_home", 15)
    await h.settle(11 * 60)
    await h.call("input_boolean", "turn_on", entity_id="input_boolean.bedroom_occupied")


SAME_WORLD = {
    "setback": (_nobody_home, {"charles": ("not_home", 5), "gaby": ("not_home", 5), "harry": ("not_home", 5)}, {}),
    "charles_away": (_charles_away, {"charles": ("not_home", 15), "gaby": ("home", None), "harry": ("home", None)}, {}),
    "far_away": (_far_away, {"charles": ("not_home", 80), "gaby": ("not_home", 80), "harry": ("not_home", 5)}, {}),
    "door_open": (_door_open, EVERYONE_HOME, {DOOR: ("on", {})}),
    "occupied_and_away": (
        _occupied_while_charles_away,
        {"charles": ("not_home", 15), "gaby": ("home", None), "harry": ("home", None)},
        {},
    ),
    "everything_at_once": (
        _everything,
        {"charles": ("not_home", 15), "gaby": ("not_home", 5), "harry": ("not_home", 5)},
        {},
    ),
}


@pytest.mark.parametrize("name", list(SAME_WORLD))
async def test_restart_in_an_unchanged_world_changes_nothing(tmp_path, name):
    drive, persons, extra = SAME_WORLD[name]
    cm_a, a = await a_house(tmp_path)
    try:
        await drive(a)
        before = snap(a)
        cm_b, b = await restart(tmp_path, a, persons, extra_states=extra)
        try:
            await b.settle(60)
            after = snap(b)
            assert after == before, {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


# --- the world changed while HA was down --------------------------------------------------


async def test_charles_got_home_while_down(tmp_path):
    cm_a, a = await a_house(tmp_path)
    try:
        await _charles_away(a)
        assert modes(a)["master_bedroom"] == "off"
        cm_b, b = await restart(tmp_path, a, EVERYONE_HOME)
        try:
            await b.settle(60)
            assert modes(b) == {r: "heat" for r in ROOMS}
            assert pid_setpoints(b) == COMFORT
            assert b.state("binary_sensor.charles_away_for_heating") == "off"
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_everyone_left_while_down(tmp_path):
    cm_a, a = await a_house(tmp_path)
    try:
        cm_b, b = await restart(tmp_path, a, LEAVE)
        try:
            await b.settle(60)
            assert pid_setpoints(b) == {r: sp - SETBACK for r, sp in COMFORT.items()}
            await b.set_person("harry", "home")
            assert pid_setpoints(b) == COMFORT
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_door_was_closed_while_down(tmp_path):
    cm_a, a = await a_house(tmp_path)
    try:
        await _door_open(a)
        assert set(modes(a).values()) == {"off"}
        cm_b, b = await restart(tmp_path, a, EVERYONE_HOME)  # door state defaults to closed
        try:
            await b.settle(60)
            assert modes(b) == {r: "heat" for r in ROOMS}
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_gaby_got_home_while_down_far_away_ends(tmp_path):
    cm_a, a = await a_house(tmp_path)
    try:
        await _far_away(a)
        assert set(modes(a).values()) == {"off"}
        persons = {"charles": ("not_home", 80), "gaby": ("home", None), "harry": ("not_home", 5)}
        cm_b, b = await restart(tmp_path, a, persons)
        try:
            await b.settle(60)
            assert b.state("binary_sensor.house_far_away") == "off"
            assert modes(b) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
            assert pid_setpoints(b)["living_room"] == COMFORT["living_room"]
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_far_away_began_while_down_waits_the_thirty_minutes(tmp_path):
    """The 30 min debounce cannot be known after a restart: it counts from start, and until it
    has run out the rooms are in setback (nobody home), not off."""
    cm_a, a = await a_house(tmp_path)
    try:
        persons = {"charles": ("not_home", 80), "gaby": ("not_home", 80), "harry": ("not_home", 5)}
        cm_b, b = await restart(tmp_path, a, persons)
        try:
            await b.settle(60)
            assert modes(b)["living_room"] == "heat"
            assert pid_setpoints(b)["living_room"] == COMFORT["living_room"] - SETBACK
            await b.settle(31 * 60)
            assert set(modes(b).values()) == {"off"}
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_boost_does_not_survive_a_restart_so_the_room_goes_back_to_policy(tmp_path):
    """boost_mode_* has `initial: false` (existing behaviour): after a restart boost is off, so a
    boosted-while-off room returns to the policy's `off`."""
    cm_a, a = await a_house(tmp_path)
    try:
        await _charles_away(a)
        await a.call("input_boolean", "turn_on", entity_id="input_boolean.boost_mode_master_bedroom")
        assert modes(a)["master_bedroom"] == "heat"
        cm_b, b = await restart(tmp_path, a, {"charles": ("not_home", 15), "gaby": ("home", None), "harry": ("home", None)})
        try:
            await b.settle(60)
            assert modes(b)["master_bedroom"] == "off"
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)
