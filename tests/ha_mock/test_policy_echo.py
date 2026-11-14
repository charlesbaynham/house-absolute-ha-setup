"""A late echo of the policy's own write is not someone turning the dial.

On 2026-11-13 `anyone_home` flickered on for 0.2 s. The policy wrote comfort, then setback, and the
physical TRV (about a second behind) reported the comfort value after the setback had been written.
The mirror copied that onto the PID, the policy read it as an edit made during setback and raised
comfort by the setback offset: setback then held the user's original comfort, and after the trip the
room would have heated 2 degrees above it."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, DEAD_TIME, EVERYONE_HOME, SETBACK, pid, policy_packages, set_comfort, trv

LR = "living_room"

class Boot:
    def __init__(self, tmp_path, persons=EVERYONE_HOME, **kw):
        self.cm = house(tmp_path, policy_packages(trvs=True), templates=load_repo_templates(), persons=persons, **kw)

    async def __aenter__(self):
        self.h = await self.cm.__aenter__()
        await set_comfort(self.h)
        return self.h

    async def __aexit__(self, *a):
        return await self.cm.__aexit__(*a)


def comfort(h, room=LR):
    return float(h.state(f"input_number.{room}_comfort_setpoint"))


async def everyone_leaves(h):
    for who in ("charles", "gaby", "harry"):
        await h.set_person(who, "not_home", 5)


async def test_a_late_trv_echo_right_after_setback_is_not_an_edit(tmp_path):
    async with Boot(tmp_path) as h:
        await everyone_leaves(h)
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK
        await h.settle(1)
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=COMFORT[LR])
        await h.settle(1)
        assert comfort(h) == COMFORT[LR]
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK, "the echo is overwritten"
        assert h.attr(trv(LR), "temperature") == COMFORT[LR] - SETBACK
        await h.settle(60 * 60)
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK
        await h.set_person("gaby", "home")
        assert h.attr(pid(LR), "temperature") == COMFORT[LR], "back to what the user set, not 2 above"


async def test_presence_flicker_with_a_late_trv_echo_leaves_comfort_alone(tmp_path):
    """The 2026-11-13 sequence: everyone gone, one person home for an instant, gone again, and the
    TRV reports the comfort value written for that instant after the setback was written."""
    async with Boot(tmp_path) as h:
        await everyone_leaves(h)
        await h.settle(60)
        await h.set_person("gaby", "home")
        assert h.attr(pid(LR), "temperature") == COMFORT[LR]
        await h.set_person("gaby", "not_home", 5)
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=COMFORT[LR])
        await h.settle(1)
        for room, value in COMFORT.items():
            assert comfort(h, room) == value, room
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK


async def test_an_edit_after_the_dead_time_is_still_an_edit(tmp_path):
    async with Boot(tmp_path) as h:
        await everyone_leaves(h)
        await h.settle(DEAD_TIME + 1)
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=20.0)
        assert h.attr(pid(LR), "temperature") == 20.0
        assert comfort(h) == 20.0 + SETBACK


async def test_an_edit_inside_the_dead_time_is_overwritten(tmp_path):
    """The price of the dead time, pinned so it is a decision and not an accident."""
    async with Boot(tmp_path) as h:
        await everyone_leaves(h)
        await h.settle(DEAD_TIME - 5)
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=20.0)
        await h.settle(1)
        assert comfort(h) == COMFORT[LR]
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK
