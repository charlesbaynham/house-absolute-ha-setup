# Mock house

A real Home Assistant core (same version as production) running this repo's own packages,
blueprints and the real `smart_thermostat` PID component. Only the outside world is faked: people
(states are set directly), Zigbee hardware (stubbed), room temperature sensors.

This is for checking heating/presence logic **before** it touches the house: restarts, races
between automations, the 30 min debounces. It does not replace a live check after a merge.

```bash
uv python install 3.14
uv venv --python 3.14 /tmp/hamock/venv
uv pip install --python /tmp/hamock/venv/bin/python homeassistant==2026.10.0 \
    pytest-homeassistant-custom-component
/tmp/hamock/venv/bin/pytest tests/ha_mock
```

`harness.py` builds a `House` (with `restart()` semantics: `house(..., restore_from=old)` boots a
fresh core primed with the old one's states, exactly what HA restores). `scenarios.py` holds the
shared helpers. A test is a story: people move, time advances (`await h.settle(seconds)`), assert on
climate modes and setpoints.

Notes:
- `await h.settle(n)` advances the mock clock then waits for automation runs. Never rely on
  `async_block_till_done` alone: an automation sitting in a `delay` would block it in real time.
- The mock follows HA's own boot: `homeassistant: start` triggers fire on `STARTED`, and the
  room control blueprints re-apply `heat` at start, like production.
- Keep the HA version in step with the live box (`ha core info` / Settings, About).
- Nothing here may contain tokens. The live API is never used by these tests.
