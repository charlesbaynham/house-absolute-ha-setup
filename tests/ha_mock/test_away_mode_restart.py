"""Away-mode state machine: survives an HA restart (the bug found 2026-11-09)."""

from .harness import house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, NOBODY_HOME, current_packages, heat_rooms, modes, setpoints

AWAY_SETPOINTS = {r: sp - 2 for r, sp in COMFORT.items()}


async def _everyone_leaves(h):
    for who in ("charles", "gaby", "harry"):
        await h.set_person(who, "not_home", 5)


async def test_away_mode_reduces_by_two_and_restores(tmp_path):
    """Baseline, no restart: this already works."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as h:
        await heat_rooms(h)
        await _everyone_leaves(h)
        assert h.state("input_select.climate_away_mode_state") == "away"
        assert setpoints(h) == AWAY_SETPOINTS
        await h.set_person("gaby", "home")
        assert h.state("input_select.climate_away_mode_state") == "home"
        assert setpoints(h) == COMFORT


async def test_restart_while_away_then_someone_returns(tmp_path):
    """THE BUG: restart while away. State and stored originals must survive, and the setpoints
    must be restored when someone gets home."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        await _everyone_leaves(a)
        assert setpoints(a) == AWAY_SETPOINTS

        async with house(
            tmp_path, current_packages(), templates=load_repo_templates(), persons=NOBODY_HOME, restore_from=a
        ) as b:
            assert b.state("binary_sensor.anyone_home") == "off"
            assert setpoints(b) == AWAY_SETPOINTS, "setpoints survive the restart"
            assert b.state("input_select.climate_away_mode_state") == "away", "state survives restart"
            for room, sp in COMFORT.items():
                assert float(b.state(f"input_number.away_mode_{room}_original_temp")) == sp
            await b.set_person("gaby", "home")
            assert b.state("input_select.climate_away_mode_state") == "home"
            assert setpoints(b) == COMFORT, "returning home restores the comfort setpoints"


async def test_restart_while_far_away_keeps_heating_off(tmp_path):
    """Far away (both > 50 km for 30 min): heating off. A restart must not lose that."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        await a.set_person("harry", "not_home", 5)
        for who in ("charles", "gaby"):
            await a.set_person(who, "not_home", 80)
        await a.settle(31 * 60)
        assert a.state("input_select.climate_away_mode_state") == "far_away", a.state(
            "input_select.climate_away_mode_state"
        )
        assert set(modes(a).values()) == {"off"}

        async with house(
            tmp_path,
            current_packages(),
            templates=load_repo_templates(),
            persons={"charles": ("not_home", 80), "gaby": ("not_home", 80), "harry": ("not_home", 5)},
            restore_from=a,
        ) as b:
            await b.settle()  # the blueprints re-apply `heat` at start; far_away must re-assert
            assert b.state("input_select.climate_away_mode_state") == "far_away"
            assert set(modes(b).values()) == {"off"}
            await b.set_person("gaby", "home")
            # The master bedroom stays off: Charles is still confirmed away (80 km), so the
            # master bedroom automation re-switches it off after the machine turns everything on.
            assert modes(b) == {"living_room": "heat", "master_bedroom": "off", "bedroom": "heat"}
            assert setpoints(b) == COMFORT


async def test_presence_changed_while_ha_was_down(tmp_path):
    """Restart in `away`, but Gaby got home during the downtime: the start trigger must notice."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        await _everyone_leaves(a)
        assert setpoints(a) == AWAY_SETPOINTS
        people = {"charles": ("not_home", 5), "gaby": ("home", None), "harry": ("not_home", 5)}
        async with house(
            tmp_path, current_packages(), templates=load_repo_templates(), persons=people, restore_from=a
        ) as b:
            await b.settle()
            assert b.state("input_select.climate_away_mode_state") == "home"
            assert setpoints(b) == COMFORT


async def test_everyone_left_while_ha_was_down(tmp_path):
    """Restart in `home`, but everyone left during the downtime: reduce, and remember the originals."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        async with house(
            tmp_path, current_packages(), templates=load_repo_templates(), persons=NOBODY_HOME, restore_from=a
        ) as b:
            await b.settle()
            assert b.state("input_select.climate_away_mode_state") == "away"
            assert setpoints(b) == AWAY_SETPOINTS
            await b.set_person("harry", "home")
            assert setpoints(b) == COMFORT


async def test_restart_at_home_changes_nothing(tmp_path):
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        async with house(
            tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME, restore_from=a
        ) as b:
            await b.settle()
            assert b.state("input_select.climate_away_mode_state") == "home"
            assert setpoints(b) == COMFORT
            assert set(modes(b).values()) == {"heat"}


async def test_start_does_not_enter_far_away_without_the_debounce(tmp_path):
    """Both far away at start while the state is `away`: stay `away` (the 30 min debounce cannot
    be known after a restart), do not jump to far_away and switch everything off."""
    async with house(tmp_path, current_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as a:
        await heat_rooms(a)
        await _everyone_leaves(a)
        far = {"charles": ("not_home", 80), "gaby": ("not_home", 80), "harry": ("not_home", 5)}
        async with house(
            tmp_path, current_packages(), templates=load_repo_templates(), persons=far, restore_from=a
        ) as b:
            await b.settle()
            assert b.state("input_select.climate_away_mode_state") == "away"
            assert modes(b)["living_room"] == "heat"
