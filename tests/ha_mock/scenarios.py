"""Shared scenario helpers for the mock-house tests (heating policy)."""

from .harness import ROOMS, House, load_repo_packages, trv_stubs

COMFORT = {"living_room": 21.0, "master_bedroom": 22.0, "bedroom": 19.0}
SETBACK = 2.0

EVERYONE_HOME = {"charles": ("home", None), "gaby": ("home", None), "harry": ("home", None)}
NOBODY_HOME = {"charles": ("not_home", 5), "gaby": ("not_home", 5), "harry": ("not_home", 5)}


def pid(room: str) -> str:
    return f"climate.{room}_trv_pid_controller"


def policy_packages(trvs: bool = False) -> dict:
    """The heating packages as the unified design has them (optionally with TRV stand-ins)."""
    pk = load_repo_packages(
        ["heating_presence", "back_door", "alarm_charles"] + [f"climate_{r}" for r in ROOMS]
    )
    if trvs:
        pk["trv_stubs"] = trv_stubs()
    return pk


async def set_comfort(h: House, setpoints: dict | None = None) -> None:
    """The user sets each room's comfort setpoint (dashboard)."""
    for room, sp in (setpoints or COMFORT).items():
        await h.call("input_number", "set_value", entity_id=f"input_number.{room}_comfort_setpoint", value=sp)


def pid_setpoints(h: House) -> dict:
    return {r: h.attr(pid(r), "temperature") for r in ROOMS}


def modes(h: House) -> dict:
    return {r: h.state(pid(r)) for r in ROOMS}


def status(h: House, room: str) -> str:
    return h.state(f"input_text.{room}_heating_status")


def trv(room: str) -> str:
    return f"climate.trv_{room}"


def trv_setpoints(h: House) -> dict:
    return {r: h.attr(trv(r), "temperature") for r in ROOMS}


def climate_writes(h: House) -> list:
    """Service calls that change what the heating does (not reads)."""
    return [c for c in h.service_calls("climate")]
