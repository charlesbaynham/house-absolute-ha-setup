"""Mutations for the heating policy (blueprints/.../trv-room-policy.yaml, packages/heating_presence.yaml).

Each is (name, file, old, new): `old` must occur exactly once. If the policy is edited and one stops
applying, `mutate.py ... --check` says so; update the text here (or drop the mutation if the behaviour
is gone). The first ten were the original set; the last five came from an independent review that
found bugs these did not cover. All fifteen are caught by tests/ha_mock as of 2026-11-10.
"""

BP = "blueprints/automation/charlesbaynham/trv-room-policy.yaml"
HP = "packages/heating_presence.yaml"

MUTATIONS = [
    ("setback reconstruction ignores the offset (edits during setback read as typed)", BP,
     "reduced_now: \"{{ mode == 'setback' }}\"", "reduced_now: \"{{ false }}\""),
    ("PID setpoint edits are ignored", BP,
     "(pid_sp - last_sp) | abs > 0.05", "(pid_sp - last_sp) | abs > 500"),
    ("no guard against half-built (unknown) presence facts", BP,
     "{{ trigger.id == 'tick'\n         or ([anyone_home, house_far_away] + follow_sensors)",
     "{{ true or ([anyone_home, house_far_away] + follow_sensors)"),
    ("no back door rule", BP,
     "{% if is_state(back_door, 'on') %}off|back door open",
     "{% if false %}off|back door open"),
    ("far away outranks occupied", BP,
     "{% elif occupied_now %}comfort|room occupied\n"
     "        {% elif follow_all_away %}off|the person this room follows is away\n"
     "        {% elif is_state(house_far_away, 'on') %}off|house far away",
     "{% elif is_state(house_far_away, 'on') %}off|house far away\n"
     "        {% elif occupied_now %}comfort|room occupied\n"
     "        {% elif follow_all_away %}off|the person this room follows is away"),
    ("every automation counts as a human 'by hand'", BP,
     "and trigger.to_state.context.user_id is not none }}", "}}"),
    ("last_written recorded AFTER the write is dropped (own echo read as an edit)", BP,
     "          # Record before writing: the echo of this write must look like our own\n"
     "          - action: input_number.set_value\n"
     "            target:\n"
     "              entity_id: !input last_written\n"
     "            data:\n"
     "              value: \"{{ want_sp }}\"\n",
     ""),
    ("latch forgets its state across a restart", HP,
     "{{ this.state == 'on' }}", "false"),
    ("latch cleared when the sensor drops, not when the person is home", HP,
     "{% if is_state('person.charles', 'home') %}",
     "{% if is_state('binary_sensor.charles_confirmed_away', 'off') %}"),
    ("the room never follows anybody", BP,
     "{{ follow_sensors | length > 0\n", "{{ false and follow_sensors | length > 0\n"),
    # --- added after the independent review ---
    ("far away ignores that someone is home (Harry alone)", HP,
     "\n             and is_state('binary_sensor.anyone_home', 'off') }}", " }}"),
    ("off rooms stop holding the comfort setpoint", BP,
     "          - if:\n              - condition: template\n"
     "                value_template: \"{{ (pid_sp - want_sp) | abs > 0.01 }}\"\n"
     "            then:\n              - action: input_number.set_value\n"
     "                target:\n                  entity_id: !input last_written\n",
     "          - if:\n              - condition: template\n"
     "                value_template: \"{{ false }}\"\n"
     "            then:\n              - action: input_number.set_value\n"
     "                target:\n                  entity_id: !input last_written\n"),
    ("occupied never clears in rooms that follow nobody", BP,
     "or (follow_sensors | length == 0", "or (false and follow_sensors | length == 0"),
    ("the policy reacts to every PID attribute change", BP,
     "    to: ~\n", ""),
    ("by-hand on needs two presses", BP,
     "value_template: \"{{ presence_off and not presence_door }}\"",
     "value_template: \"{{ false }}\""),
]
