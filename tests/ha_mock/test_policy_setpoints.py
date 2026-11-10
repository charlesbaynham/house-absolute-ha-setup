"""Setpoints: comfort is the user's number, the PID's is derived, TRV edits flow back."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, SETBACK, modes, pid, pid_setpoints, policy_packages, set_comfort, trv, trv_setpoints

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


async def test_the_physical_trv_follows_the_pid_setpoint(tmp_path):
    async with Boot(tmp_path) as h:
        await h.settle()
        assert trv_setpoints(h)["living_room"] == COMFORT["living_room"]


async def test_editing_the_trv_in_comfort_changes_the_comfort_setpoint(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=23.0)
        assert h.attr(pid(LR), "temperature") == 23.0
        assert comfort(h) == 23.0
        assert float(h.state("input_number.living_room_policy_last_setpoint")) == 23.0
        assert h.attr(pid(LR), "temperature") == 23.0, "and nothing fights it"


async def test_editing_the_trv_during_setback_stores_comfort_plus_the_offset(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert h.attr(pid(LR), "temperature") == COMFORT[LR] - SETBACK  # 19
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=20.0)
        assert h.attr(pid(LR), "temperature") == 20.0
        assert comfort(h) == 22.0, "the 20 they asked for now, 22 when someone is home again"
        await h.set_person("gaby", "home")
        assert h.attr(pid(LR), "temperature") == 22.0


async def test_changing_comfort_on_the_dashboard_moves_the_pid_and_the_trv(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_number", "set_value", entity_id=f"input_number.{LR}_comfort_setpoint", value=20.5)
        assert h.attr(pid(LR), "temperature") == 20.5
        assert h.attr(trv(LR), "temperature") == 20.5


async def test_setback_applies_to_the_physical_trv_too_and_comfort_is_untouched(tmp_path):
    async with Boot(tmp_path) as h:
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert h.attr(trv(LR), "temperature") == COMFORT[LR] - SETBACK
        assert comfort(h) == COMFORT[LR]


async def test_edit_while_the_room_is_off_becomes_the_comfort_setpoint(tmp_path):
    async with Boot(tmp_path) as h:
        await h.call("input_boolean", "turn_on", entity_id="input_boolean.living_room_heating_disabled")
        assert modes(h)[LR] == "off"
        await h.call("climate", "set_temperature", entity_id=trv(LR), temperature=18.5)
        assert comfort(h) == 18.5
        assert modes(h)[LR] == "off"
        await h.call("input_boolean", "turn_off", entity_id="input_boolean.living_room_heating_disabled")
        assert h.attr(pid(LR), "temperature") == 18.5


async def test_restart_never_corrupts_comfort(tmp_path):
    """Repeated restarts in every presence state: comfort, PID and TRV setpoints stay put."""
    cm = house(tmp_path, policy_packages(trvs=True), templates=load_repo_templates(), persons=EVERYONE_HOME)
    a = await cm.__aenter__()
    cms = [cm]
    try:
        await set_comfort(a)
        for who in ("charles", "gaby", "harry"):
            await a.set_person(who, "not_home", 5)
        want_pid, want_trv = pid_setpoints(a), trv_setpoints(a)
        prev = a
        for _ in range(3):
            nxt = house(
                tmp_path,
                policy_packages(trvs=True),
                templates=load_repo_templates(),
                persons={"charles": ("not_home", 5), "gaby": ("not_home", 5), "harry": ("not_home", 5)},
                restore_from=prev,
            )
            cms.append(nxt)
            prev = await nxt.__aenter__()
            await prev.settle(60)
            assert pid_setpoints(prev) == want_pid
            assert trv_setpoints(prev) == want_trv
            assert {r: float(prev.state(f"input_number.{r}_comfort_setpoint")) for r in COMFORT} == COMFORT
    finally:
        for c in reversed(cms):
            await c.__aexit__(None, None, None)


async def test_clamped_setback_does_not_make_comfort_drift(tmp_path):
    """Comfort 8 with a 2 degree setback wants 6, clamped to the 7 minimum. The policy's own echo
    (PID now at 7) must not be read as the user asking for 7 + 2 = 9."""
    async with Boot(tmp_path) as h:
        await h.call("input_number", "set_value", entity_id=f"input_number.{LR}_comfort_setpoint", value=8.0)
        for who in ("charles", "gaby", "harry"):
            await h.set_person(who, "not_home", 5)
        assert h.attr(pid(LR), "temperature") == 7.0
        await h.settle(30 * 60)
        assert comfort(h) == 8.0
        await h.set_person("gaby", "home")
        assert h.attr(pid(LR), "temperature") == 8.0
