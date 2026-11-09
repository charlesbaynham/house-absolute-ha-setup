"""First deployment of the unified policy onto the live house.

The new helpers/latches have never existed, so nothing is restored for them; the climate entities
come back exactly as the old config left them (rooms reduced / off). The policy must adopt that
without changing anything: no setpoint jumps, no heating switched on for a moment."""

from .harness import ROOMS, house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, climate_writes, modes, pid, pid_setpoints, policy_packages

NEW = (
    "_comfort_setpoint",
    "_policy_last_setpoint",
    "_occupied",
    "_heating_status",
    "heating_policy",
    "house_far_away",
    "charles_away_for_heating",
)


def only_old_world(entity_id: str) -> bool:
    return not any(tag in entity_id for tag in NEW)


async def old_world(tmp_path, living, master, bedroom, master_mode="off"):
    """A house as the OLD config left it (same entities, no policy helpers), returned running."""
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm.__aenter__()
    # The old config had no policy: stop it fighting while the old world is being built
    for room in ROOMS:
        await a.call("automation", "turn_off", entity_id=f"automation.{room}_heating_policy")
    for room, sp, mode in (("living_room", living, "heat"), ("master_bedroom", master, master_mode), ("bedroom", bedroom, "heat")):
        await a.call("climate", "set_temperature", entity_id=pid(room), temperature=sp)
        await a.call("climate", "set_hvac_mode", entity_id=pid(room), hvac_mode=mode)
    return cm, a


async def test_live_state_today_is_adopted_without_a_single_change(tmp_path):
    """Today's live state: nobody home (setpoints reduced 21->19, 19->17), Charles 15 km away and
    the master bedroom off at 21.0. Unseeded: comfort is reconstructed from the PID setpoint."""
    cm, a = await old_world(tmp_path, living=19.0, master=21.0, bedroom=17.0)
    try:
        persons = {"charles": ("not_home", 15), "gaby": ("not_home", 5), "harry": ("not_home", 5)}
        cm2 = house(
            tmp_path,
            policy_packages(),
            templates=load_repo_templates(),
            persons=persons,
            restore_from=a,
            restore_filter=only_old_world,
        )
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            # Adopted, not changed: modes and setpoints are exactly what the old config left
            assert modes(b) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
            assert pid_setpoints(b) == {"living_room": 19.0, "master_bedroom": 21.0, "bedroom": 17.0}
            # and the comfort setpoints were reconstructed (setpoint + setback while nobody is home)
            assert float(b.state("input_number.living_room_comfort_setpoint")) == 21.0
            assert float(b.state("input_number.bedroom_comfort_setpoint")) == 19.0
            # master: 21.0 while nobody is home reads as comfort 23 (the old machine had reduced
            # it too). This is why the deployment seeds the comfort helpers by hand instead.
            assert float(b.state("input_number.master_bedroom_comfort_setpoint")) == 23.0
            # the latches adopted the live values at once (no 10 / 30 minute wait)
            assert b.state("binary_sensor.charles_away_for_heating") == "on"
            # nothing was switched on, even briefly, and no setpoint was written
            writes = climate_writes(b)
            assert not [c for c in writes if c[1] in ("turn_on", "set_hvac_mode") and c[2].get("hvac_mode") != "off"
                        or c[1] == "turn_on"], writes
            assert not [c for c in writes if c[1] == "set_temperature"], writes
            # Gaby gets home: everything returns to comfort
            await b.set_person("gaby", "home")
            assert pid_setpoints(b) == {"living_room": 21.0, "master_bedroom": 21.0, "bedroom": 19.0}
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)


async def test_seeded_comfort_setpoints_are_kept_exactly(tmp_path):
    """The deployment plan: comfort helpers are seeded (21 / 22 / 19, the old machine's stored
    originals) before the merge. The first run keeps them and just adopts the PID setpoints."""
    cm, a = await old_world(tmp_path, living=19.0, master=21.0, bedroom=17.0)
    try:
        for room, v in COMFORT.items():
            await a.call("input_number", "set_value", entity_id=f"input_number.{room}_comfort_setpoint", value=v)
        persons = {"charles": ("not_home", 15), "gaby": ("not_home", 5), "harry": ("not_home", 5)}
        seed = lambda e: only_old_world(e) or e.endswith("_comfort_setpoint")  # noqa: E731
        cm2 = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons,
                    restore_from=a, restore_filter=seed)
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            assert {r: float(b.state(f"input_number.{r}_comfort_setpoint")) for r in ROOMS} == COMFORT
            assert modes(b) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
            assert pid_setpoints(b) == {"living_room": 19.0, "master_bedroom": 21.0, "bedroom": 17.0}
            assert not [c for c in climate_writes(b) if c[1] == "set_temperature"]
            # Charles gets home: the master bedroom goes to its real comfort setpoint, 22
            await b.set_person("charles", "home")
            await b.set_person("gaby", "home")
            assert pid_setpoints(b) == COMFORT
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)


async def test_migration_on_an_ordinary_day_changes_nothing(tmp_path):
    cm, a = await old_world(tmp_path, living=21.0, master=22.0, bedroom=19.0, master_mode="heat")
    try:
        cm2 = house(
            tmp_path,
            policy_packages(),
            templates=load_repo_templates(),
            persons=EVERYONE_HOME,
            restore_from=a,
            restore_filter=only_old_world,
        )
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            assert modes(b) == {r: "heat" for r in ROOMS}
            assert pid_setpoints(b) == COMFORT
            assert {r: float(b.state(f"input_number.{r}_comfort_setpoint")) for r in ROOMS} == COMFORT
            assert not [c for c in climate_writes(b) if c[1] == "set_temperature"]
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)


async def test_migration_while_far_away(tmp_path):
    cm, a = await old_world(tmp_path, living=19.0, master=20.0, bedroom=17.0, master_mode="off")
    try:
        for r in ROOMS:
            await a.call("climate", "set_hvac_mode", entity_id=pid(r), hvac_mode="off")
        persons = {"charles": ("not_home", 80), "gaby": ("not_home", 80), "harry": ("not_home", 5)}
        cm2 = house(
            tmp_path,
            policy_packages(),
            templates=load_repo_templates(),
            persons=persons,
            restore_from=a,
            restore_filter=only_old_world,
        )
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            assert b.state("binary_sensor.house_far_away") == "on", "adopted: no 30 minute wait"
            assert set(modes(b).values()) == {"off"}
            # the old machine had reduced 21 -> 19 before going far away: reconstruct 21
            assert float(b.state("input_number.living_room_comfort_setpoint")) == 21.0
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)
