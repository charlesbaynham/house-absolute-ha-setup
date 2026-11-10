"""The 'switched off' switch (a deliberate manual off), and by-hand on/off."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, modes, pid_setpoints, policy_packages, set_comfort, status

LR = "climate.living_room_trv_pid_controller"


class Boot:
    def __init__(self, tmp_path, persons=EVERYONE_HOME, **kw):
        self.cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        return await self.cm.__aexit__(*a)


async def test_turning_heat_off_by_hand_switches_the_room_off_and_it_stays_off(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("climate", "turn_off", by_hand=True, entity_id=LR)
        assert h.state("input_boolean.living_room_heating_disabled") == "on"
        assert modes(h)["living_room"] == "off"
        assert status(h, "living_room").startswith("off - room switched off")
        # the policy does not turn it back on, however often it reconciles
        await h.settle(35 * 60)
        assert modes(h)["living_room"] == "off"
        # other rooms unaffected
        assert modes(h)["bedroom"] == "heat"


async def test_a_switched_off_room_ignores_presence_boost_and_occupied(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("climate", "turn_off", by_hand=True, entity_id=LR)
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.living_room_occupied")
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.boost_mode_living_room")
        assert modes(h)["living_room"] == "off"


async def test_turning_heat_on_by_hand_ends_the_switch_off(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("climate", "turn_off", by_hand=True, entity_id=LR)
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id=LR, hvac_mode="heat")
        assert h.state("input_boolean.living_room_heating_disabled") == "off"
        assert modes(h)["living_room"] == "heat"
        assert h.state("input_boolean.living_room_occupied") == "off", "not 'occupied': just switched back on"


async def test_the_switch_can_be_flipped_from_the_dashboard_too(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.bedroom_heating_disabled")
        assert modes(h)["bedroom"] == "off"
        await h.call("input_boolean", "turn_off", entity_id="input_boolean.bedroom_heating_disabled")
        assert modes(h)["bedroom"] == "heat"


async def test_off_by_an_automation_is_not_a_manual_switch_off(tmp_path):
    """Only a human's off counts. An automation turning the PID off is simply reverted."""
    async with Boot(tmp_path) as h:
        await h.call("climate", "turn_off", entity_id=LR)  # no user context
        assert h.state("input_boolean.living_room_heating_disabled") == "off"
        assert modes(h)["living_room"] == "heat"


async def test_switched_off_room_survives_restart(tmp_path):
    cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm.__aenter__()
    try:
        await set_comfort(a)
        await a.call("climate", "turn_off", by_hand=True, entity_id=LR)
        cm2 = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME, restore_from=a)
        b = await cm2.__aenter__()
        try:
            await b.settle(60)
            assert modes(b)["living_room"] == "off"
            assert "heat" not in b.climate_modes_seen(LR)[1:] or b.climate_modes_seen(LR) == ["off"]
            assert b.state("input_boolean.living_room_heating_disabled") == "on"
        finally:
            await cm2.__aexit__(None, None, None)
    finally:
        await cm.__aexit__(None, None, None)
