from .harness import ROOMS, house, load_repo_packages, load_repo_templates


async def test_house_boots_and_restarts(tmp_path):
    pk = load_repo_packages(
        ["climate_away_mode", "back_door", "alarm_charles", "climate_master_bedroom_away"]
        + [f"climate_{r}" for r in ROOMS]
    )
    people = {"charles": ("home", None), "gaby": ("home", None), "harry": ("home", None)}
    async with house(tmp_path, pk, templates=load_repo_templates(), persons=people) as a:
        assert a.state("binary_sensor.anyone_home") == "on"
        await a.call("input_select", "select_option", entity_id="input_select.climate_away_mode_state", option="away")
        assert a.state("automation.master_bedroom_restart_heating_at_4am") == "off"
        async with house(tmp_path, pk, templates=load_repo_templates(), persons=people, restore_from=a) as b:
            # `initial: home` wins over the restored `away`: the bug under investigation.
            print("after restart:", b.state("input_select.climate_away_mode_state"))
            assert b.state("automation.master_bedroom_restart_heating_at_4am") == "off"
