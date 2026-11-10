"""The policy rules in steady state (no restart): presence, person-follow, far away."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, NOBODY_HOME, SETBACK, modes, pid_setpoints, policy_packages, set_comfort, status

ALL = ("living_room", "master_bedroom", "bedroom")


async def boot(tmp_path, persons=EVERYONE_HOME, **kw):
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons, **kw)
    h = await cm.__aenter__()
    await set_comfort(h)
    return cm, h


async def test_everyone_home_is_comfort(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        assert modes(h) == {r: "heat" for r in ALL}
        assert pid_setpoints(h) == COMFORT
        assert status(h, "master_bedroom").startswith("comfort - someone home")
    finally:
        await cm.__aexit__(None, None, None)


async def test_nobody_home_is_setback_and_return_restores(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert modes(h) == {r: "heat" for r in ALL}
        assert pid_setpoints(h) == {r: sp - SETBACK for r, sp in COMFORT.items()}
        assert status(h, "living_room").startswith("setback - nobody home")
        # comfort is untouched: nothing was "saved", it is derived
        assert {r: float(h.state(f"input_number.{r}_comfort_setpoint")) for r in ALL} == COMFORT
        await h.set_person("harry", "home")
        assert pid_setpoints(h) == COMFORT
    finally:
        await cm.__aexit__(None, None, None)


async def test_charles_away_switches_master_bedroom_off_after_ten_minutes(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("charles", "not_home", 15)
        assert h.state("binary_sensor.charles_confirmed_away") == "on"
        await h.settle(9 * 60)
        assert modes(h)["master_bedroom"] == "heat", "not before the 10 minute debounce"
        await h.settle(2 * 60)
        assert modes(h) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"], "Gaby is home: no setback"
        assert "follows is away" in status(h, "master_bedroom")
    finally:
        await cm.__aexit__(None, None, None)


async def test_charles_away_and_house_empty_master_off_others_setback(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        await h.set_person("gaby", "not_home", 5)
        await h.set_person("harry", "not_home", 5)
        assert modes(h) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"] - SETBACK
        assert pid_setpoints(h)["bedroom"] == COMFORT["bedroom"] - SETBACK
    finally:
        await cm.__aexit__(None, None, None)


async def test_charles_home_restores_master_bedroom_at_once(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        assert modes(h)["master_bedroom"] == "off"
        await h.set_person("charles", "home")
        assert modes(h)["master_bedroom"] == "heat"
        assert pid_setpoints(h)["master_bedroom"] == COMFORT["master_bedroom"]
        assert h.state("binary_sensor.charles_away_for_heating") == "off"
    finally:
        await cm.__aexit__(None, None, None)


async def test_stale_location_does_not_bring_the_heating_back(tmp_path):
    """The confirmed-away sensor goes off (stale / under 10 km) while he is still not home: the
    master bedroom stays off until person.charles is `home`."""
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("charles", "not_home", 15)
        await h.settle(11 * 60)
        await h.set_person("charles", "not_home", 5)  # nearer: sensor off, still not home
        assert h.state("binary_sensor.charles_confirmed_away") == "off"
        await h.settle(30 * 60)
        assert modes(h)["master_bedroom"] == "off"
        await h.set_person("charles", "home")
        assert modes(h)["master_bedroom"] == "heat"
    finally:
        await cm.__aexit__(None, None, None)


async def test_short_trip_never_trips_the_ten_minute_debounce(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("charles", "not_home", 15)
        await h.settle(5 * 60)
        await h.set_person("charles", "home")
        await h.settle(20 * 60)
        assert modes(h)["master_bedroom"] == "heat"
        assert h.state("binary_sensor.charles_away_for_heating") == "off"
    finally:
        await cm.__aexit__(None, None, None)


async def test_far_away_needs_thirty_minutes_then_all_off(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("harry", "not_home", 5)
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"] - SETBACK
        await h.settle(29 * 60)
        assert modes(h)["living_room"] == "heat"
        await h.settle(2 * 60)
        assert set(modes(h).values()) == {"off"}
        assert h.state("binary_sensor.house_far_away") == "on"
    finally:
        await cm.__aexit__(None, None, None)


async def test_far_away_then_gaby_home_restores_living_but_master_follows_charles(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        await h.set_person("harry", "not_home", 5)
        await h.set_person("charles", "not_home", 80)
        await h.set_person("gaby", "not_home", 80)
        await h.settle(31 * 60)
        assert set(modes(h).values()) == {"off"}
        await h.set_person("gaby", "home")
        assert modes(h) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
        assert pid_setpoints(h)["living_room"] == COMFORT["living_room"]
        assert h.state("binary_sensor.house_far_away") == "off"
    finally:
        await cm.__aexit__(None, None, None)


async def test_unknown_presence_never_reduces_heating(tmp_path):
    cm, h = await boot(tmp_path)
    try:
        for ent in ("binary_sensor.anyone_home", "binary_sensor.house_far_away"):
            await h.set_state(ent, "unavailable")
        await h.settle(10 * 60)
        assert modes(h) == {r: "heat" for r in ALL}
        assert pid_setpoints(h) == COMFORT
    finally:
        await cm.__aexit__(None, None, None)
