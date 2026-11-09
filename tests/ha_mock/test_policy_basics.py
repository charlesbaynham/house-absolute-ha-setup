from .harness import ROOMS, house, load_repo_templates
from .scenarios import COMFORT, EVERYONE_HOME, modes, pid_setpoints, policy_packages, set_comfort, status


async def test_boots_and_heats_everywhere(tmp_path):
    async with house(tmp_path, policy_packages(), templates=load_repo_templates(), persons=EVERYONE_HOME) as h:
        await h.settle()
        assert set(modes(h).values()) == {"heat"}, modes(h)
        for r in ROOMS:
            print(r, status(h, r), pid_setpoints(h)[r], h.state(f"input_number.{r}_comfort_setpoint"))
        await set_comfort(h)
        assert pid_setpoints(h) == COMFORT
