# Mock house

A real Home Assistant core (same version as production) running this repo's own packages,
blueprints and the real `smart_thermostat` PID component. Only the outside world is faked: people
(states are set directly), Zigbee hardware (stubbed), room temperature sensors.

This is for checking heating/presence logic **before** it touches the house: restarts, races
between automations, the 30 min debounces. It does not replace a live check after a merge.

```bash
.claude/skills/ha-test-harness/scripts/setup_mock.sh --run     # venv + HA core + tests (see that skill)
.claude/skills/ha-test-harness/scripts/run_mock_tests.sh       # later runs
```

The skill `ha-test-harness` also has the mutation-testing runner and the live-API helpers.

`harness.py` builds a `House` (with `restart()` semantics: `house(..., restore_from=old)` boots a
fresh core primed with the old one's states, exactly what HA restores). `scenarios.py` holds the
shared helpers. A test is a story: people move, time advances (`await h.settle(seconds)`), assert on
climate modes and setpoints.

Notes:
- Restarts go through HA's own restore store (JSON round trip, including the extra stored data that
  trigger-based template entities restore from), and the clock is frozen: it only moves through
  `await h.settle(seconds)`, so `for:` debounces and `delay`s behave as in production.
- `await h.settle(n)` advances the mock clock then waits for automation runs. Never rely on
  `async_block_till_done` alone: an automation sitting in a `delay` would block it in real time.
- The mock follows HA's own boot: `homeassistant: start` triggers fire on `STARTED`. People exist
  before boot here, unlike a real start where `person.*` can change during boot: expect first-deploy
  blips the mock cannot show.
- Keep the HA version in step with the live box (`ha_live.py version`, or Settings, About).
- Nothing here may contain tokens. The live API is never used by these tests.
