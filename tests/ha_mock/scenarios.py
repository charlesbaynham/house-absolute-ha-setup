"""Shared scenario helpers for the mock-house tests."""

from .harness import ROOMS, House, house, load_repo_packages, load_repo_templates

PID = "climate.{room}_trv_pid_controller"
COMFORT = {"living_room": 21.0, "master_bedroom": 22.0, "bedroom": 19.0}

EVERYONE_HOME = {"charles": ("home", None), "gaby": ("home", None), "harry": ("home", None)}
NOBODY_HOME = {"charles": ("not_home", 5), "gaby": ("not_home", 5), "harry": ("not_home", 5)}


def pid(room: str) -> str:
    return PID.format(room=room)


def current_packages() -> dict:
    """The heating-related packages as they are in the repo today."""
    return load_repo_packages(
        ["climate_away_mode", "back_door", "alarm_charles", "climate_master_bedroom_away"]
        + [f"climate_{r}" for r in ROOMS]
    )


async def heat_rooms(h: House, setpoints: dict | None = None) -> None:
    """Put every room into `heat` at its comfort setpoint, like the live house on a normal day."""
    for room, sp in (setpoints or COMFORT).items():
        await h.call("climate", "set_hvac_mode", entity_id=pid(room), hvac_mode="heat")
        await h.call("climate", "set_temperature", entity_id=pid(room), temperature=sp)


def setpoints(h: House) -> dict:
    return {r: h.attr(pid(r), "temperature") for r in ROOMS}


def modes(h: House) -> dict:
    return {r: h.state(pid(r)) for r in ROOMS}
