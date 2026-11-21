"""The back door heating hold: the heating stays off for an hour after the door closes."""

from .harness import ROOMS, house, load_repo_templates
from .scenarios import (
    COMFORT,
    DOOR,
    EVERYONE_HOME,
    HOLD,
    HOLD_TIMER,
    modes,
    pid_setpoints,
    policy_packages,
    set_comfort,
    status,
)

HOUR = 3600
ALL_OFF = {r: "off" for r in ROOMS}
ALL_HEAT = {r: "heat" for r in ROOMS}


class Boot:
    def __init__(self, tmp_path, persons=EVERYONE_HOME, **kw):
        self.cm = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        await self.cm.__aexit__(*a)


async def open_then_close(h):
    await h.set_state(DOOR, "on")
    await h.set_state(DOOR, "off")


async def test_closing_the_door_starts_an_hour_long_hold(tmp_path):
    async with Boot(tmp_path) as h:
        await open_then_close(h)
        assert h.state(HOLD) == "on"
        assert h.state(HOLD_TIMER) == "active"
        assert modes(h) == ALL_OFF
        assert "hold" in status(h, "living_room")
        await h.settle(59 * 60)
        assert h.state(HOLD) == "on"
        assert modes(h) == ALL_OFF
        await h.settle(2 * 60)
        assert h.state(HOLD) == "off"
        assert h.state(HOLD_TIMER) == "idle"
        assert modes(h) == ALL_HEAT
        assert pid_setpoints(h) == COMFORT


async def test_switching_the_hold_off_ends_it_at_once(tmp_path):
    async with Boot(tmp_path) as h:
        await open_then_close(h)
        await h.settle(60)
        await h.call("input_boolean", "turn_off", by_hand=True, entity_id=HOLD)
        assert h.state(HOLD_TIMER) == "idle"
        assert modes(h) == ALL_HEAT
        await h.settle(HOUR + 60)
        assert modes(h) == ALL_HEAT, "the cancelled timer must not do anything later"


async def test_the_hour_counts_from_the_last_close(tmp_path):
    async with Boot(tmp_path) as h:
        await open_then_close(h)
        await h.settle(40 * 60)
        await open_then_close(h)
        await h.settle(40 * 60)  # 80 min after the first close, 40 after the second
        assert h.state(HOLD) == "on"
        assert modes(h) == ALL_OFF
        await h.settle(21 * 60)
        assert modes(h) == ALL_HEAT


async def test_an_hour_passing_with_the_door_open_changes_nothing_until_it_closes(tmp_path):
    async with Boot(tmp_path) as h:
        await open_then_close(h)
        await h.set_state(DOOR, "on")
        await h.settle(HOUR + 60)
        assert h.state(HOLD) == "off"
        assert modes(h) == ALL_OFF, "door still open"
        await h.set_state(DOOR, "off")
        assert h.state(HOLD) == "on"
        assert modes(h) == ALL_OFF


async def test_turning_the_heating_on_by_hand_during_the_hold_is_reverted(tmp_path):
    async with Boot(tmp_path) as h:
        await open_then_close(h)
        await h.call("climate", "set_hvac_mode", by_hand=True, entity_id="climate.living_room_trv_pid_controller", hvac_mode="heat")
        assert modes(h)["living_room"] == "off"
        assert h.state("input_boolean.living_room_occupied") == "off"


async def test_switching_the_hold_on_by_hand_holds_for_an_hour(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", by_hand=True, entity_id=HOLD)
        assert h.state(HOLD_TIMER) == "active"
        assert modes(h) == ALL_OFF
        await h.settle(HOUR + 60)
        assert modes(h) == ALL_HEAT


async def test_hold_survives_a_restart_and_ends_on_time(tmp_path):
    cm_a = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm_a.__aenter__()
    try:
        await set_comfort(a)
        await open_then_close(a)
        await a.settle(30 * 60)
        cm_b = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME, restore_from=a)
        b = await cm_b.__aenter__()
        try:
            await b.settle(60)
            assert b.state(HOLD) == "on"
            assert modes(b) == ALL_OFF
            await b.settle(31 * 60)
            assert b.state(HOLD) == "off"
            assert modes(b) == ALL_HEAT
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)


async def test_a_hold_that_expired_while_down_is_cleared(tmp_path):
    cm_a = house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm_a.__aenter__()
    try:
        await set_comfort(a)
        await open_then_close(a)
        # Reboot with the stored state of 'hold on, nothing counting' (what a long outage leaves)
        cm_b = house(
            tmp_path,
            policy_packages(),
            templates=load_repo_templates(),
            persons=EVERYONE_HOME,
            restore_from=a,
            restore_filter=lambda ent: not ent.startswith("timer."),
        )
        b = await cm_b.__aenter__()
        try:
            await b.settle(60)
            assert b.state(HOLD_TIMER) == "idle"
            assert b.state(HOLD) == "off"
            assert modes(b) == ALL_HEAT
        finally:
            await cm_b.__aexit__(None, None, None)
    finally:
        await cm_a.__aexit__(None, None, None)
