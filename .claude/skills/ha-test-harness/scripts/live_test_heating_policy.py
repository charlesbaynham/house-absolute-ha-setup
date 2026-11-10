#!/usr/bin/env python3
"""Live simulation of the heating policy, run after a merge (14 checks; restores everything).

    live_test_heating_policy.py [--force]

Drives the paths that are safe to drive on the real house: the occupied switch, a by-hand turn-on
and turn-off through the real API user context, the switched-off switch, a dashboard comfort edit and
the physical-TRV mirror (both directions). It deliberately does NOT spoof presence: setback, far away
and the back door stay mock-only, because `binary_sensor.anyone_home` also arms "Vacuum when everyone
leaves" (20 h guard) and "Turn off all lights when everyone leaves".

Preconditions (it refuses to start otherwise, unless --force): Gaby is home and Charles is not, so the
master bedroom is off because it follows Charles. Adapt ROOMS / the precondition for other situations.
Room helpers: {room}_occupied, {room}_heating_disabled, {room}_comfort_setpoint, PID climate
climate.{room}_trv_pid_controller and the physical TRV climate.trv_{room}.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ha_live as ha  # noqa: E402
from live_testkit import Run  # noqa: E402

ROOMS = ("living_room", "master_bedroom", "bedroom")
pid = lambda r: f"climate.{r}_trv_pid_controller"  # noqa: E731
trv = lambda r: f"climate.trv_{r}"  # noqa: E731
comfort = lambda r: f"input_number.{r}_comfort_setpoint"  # noqa: E731

if "--force" not in sys.argv:
    gaby, charles = ha.st("person.gaby")["state"], ha.st("person.charles")["state"]
    if not (gaby == "home" and charles != "home"):
        sys.exit(f"precondition not met (gaby={gaby}, charles={charles}): want Gaby home, Charles away. --force to override")

entities = [e for r in ROOMS for e in (pid(r), trv(r), comfort(r), f"input_boolean.{r}_occupied",
                                       f"input_boolean.{r}_heating_disabled")]
saved = {r: float(ha.st(comfort(r))["state"]) for r in ROOMS}


def restore():
    for r in ROOMS:
        ha.svc("input_boolean", "turn_off", {"entity_id": f"input_boolean.{r}_occupied"})
        ha.svc("input_boolean", "turn_off", {"entity_id": f"input_boolean.{r}_heating_disabled"})
        ha.svc("input_number", "set_value", {"entity_id": comfort(r), "value": saved[r]})


with Run(entities, restore_steps=restore) as t:
    status = lambda r: ha.st(f"input_text.{r}_heating_status")["state"]  # noqa: E731
    # 1. occupied switch, master bedroom (it is off because Charles is away)
    t.service("input_boolean", "turn_on", {"entity_id": "input_boolean.master_bedroom_occupied"})
    t.check("1a occupied -> master heats", t.wait(lambda: t.state(pid("master_bedroom")) == "heat"), status("master_bedroom"))
    t.check("1b status says occupied", "room occupied" in status("master_bedroom"))
    t.service("input_boolean", "turn_off", {"entity_id": "input_boolean.master_bedroom_occupied"})
    t.check("1c occupied off -> master off again", t.wait(lambda: t.state(pid("master_bedroom")) == "off"))

    # 2. by-hand ON (a call through the API carries a user context): one press -> occupied
    t.service("climate", "set_hvac_mode", {"entity_id": pid("master_bedroom"), "hvac_mode": "heat"})
    t.check("2a by-hand heat -> occupied switch on", t.wait(lambda: t.state("input_boolean.master_bedroom_occupied") == "on"))
    t.check("2b ...and the room stays on", t.state(pid("master_bedroom")) == "heat")
    t.service("input_boolean", "turn_off", {"entity_id": "input_boolean.master_bedroom_occupied"})
    t.check("2c cleared -> off", t.wait(lambda: t.state(pid("master_bedroom")) == "off"))

    # 3. by-hand OFF in a heated room -> switched-off switch; by-hand ON clears it
    t.service("climate", "turn_off", {"entity_id": pid("living_room")})
    t.check("3a by-hand off -> switched off", t.wait(lambda: t.state("input_boolean.living_room_heating_disabled") == "on"))
    import time; time.sleep(8)  # noqa: E702
    t.check("3b stays off", t.state(pid("living_room")) == "off", status("living_room"))
    t.service("climate", "set_hvac_mode", {"entity_id": pid("living_room"), "hvac_mode": "heat"})
    t.check("3c by-hand on -> back on, switch cleared", t.wait(
        lambda: t.state(pid("living_room")) == "heat" and t.state("input_boolean.living_room_heating_disabled") == "off"))
    t.check("3d not marked occupied", t.state("input_boolean.living_room_occupied") == "off")

    # 4. dashboard comfort edit reaches the PID and the physical TRV
    t.service("input_number", "set_value", {"entity_id": comfort("bedroom"), "value": saved["bedroom"] + 0.5})
    t.check("4a comfort edit -> PID", t.wait(lambda: t.attr(pid("bedroom"), "temperature") == saved["bedroom"] + 0.5))
    t.check("4b ...and the physical TRV", t.wait(lambda: t.attr(trv("bedroom"), "temperature") == saved["bedroom"] + 0.5, 60))

    # 5. editing the physical TRV flows back into comfort
    t.service("climate", "set_temperature", {"entity_id": trv("bedroom"), "temperature": saved["bedroom"]})
    t.check("5a TRV edit -> comfort", t.wait(lambda: float(t.state(comfort("bedroom"))) == saved["bedroom"], 60))
    t.check("5b PID follows", t.attr(pid("bedroom"), "temperature") == saved["bedroom"])
