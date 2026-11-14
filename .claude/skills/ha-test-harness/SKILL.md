---
name: ha-test-harness
description: >
  Scripts and know-how to test Home Assistant config changes before and after they reach the house:
  the MOCK HOUSE (a real HA core running this repo's YAML, in tests/ha_mock), MUTATION TESTING of the
  tests, and the LIVE API helpers for post-merge simulations (token handling, snapshot/restore test
  kit, orphaned-entity cleanup).

  TRIGGER THIS SKILL WHEN:
  - Changing heating, presence, debounce or restart-sensitive logic (packages/, blueprints/)
  - Opening a PR that changes HA behaviour and you need evidence it works, including across restarts
  - Merging such a PR: WORKSPACE.md requires a live simulation afterwards
  - "Set up the mock house / test harness", "run the mock tests", "mutation test", "clean up orphaned entities"
  - You need the live HA token for read-only checks or a simulation
metadata:
  version: 1
---

# HA test harness

Three tools, used in this order around a change. The harness itself is `tests/ha_mock/` (read its
README); this skill is the scripts that set it up, drive it and test with it. All scripts are in
`scripts/` and keep their state **outside the repo** (`/tmp/hamock`, `/tmp/ha-live`): `gitsync.sh`
commits and pushes everything under `/config` and nothing scans for secrets.

## 1. Mock house: before the PR

A real Home Assistant core (same version as production) running this repo's own packages, blueprints
and the real `smart_thermostat`. Only people, Zigbee hardware and room sensors are faked.

```bash
scripts/setup_mock.sh --ha-version "$(scripts/ha_live.py version)" --run   # first time (~1.5 min); version from the live box
scripts/run_mock_tests.sh                    # whole suite (~70 s); extra pytest args pass through
scripts/run_mock_tests.sh -k restart -x
```

Without a token yet, `--ha-version 2026.10.0` (the default) is right until HA is upgraded.
⚠️ A newer HA may have no matching `pytest-homeassistant-custom-component` yet: with 2026.11.1 `uv` resolved
0.2.1 and pytest died on import (`legacy_api_password`, `ast.Str`). Use the newest HA the plugin has a release
for (2026.10.0 on 2026-11-14) and say in the PR that the mock runs an older core than the live box. Python 3.14 comes
from `uv`; the venv is `$HAMOCK_DIR/venv` (default `/tmp/hamock`) and is rebuilt per container.

Writing a scenario (copy a file in `tests/ha_mock/`): `house(...)` boots a house with people in given
states; `house(..., restore_from=old)` is a **restart** primed with HA's own restore data; `await
h.settle(seconds)` is the only way time moves (frozen clock; `for:` debounces and `delay`s behave as in
production); `h.call(..., by_hand=True)` gives a service call a user context (the dashboard / app);
`h.climate_modes_seen(entity)` shows every state an entity went through (catches blips). Assert on modes and
setpoints. A restart test must compare the house **before and after** (see `test_policy_restart.py`).

What the mock gets right and what it cannot show:
- Right: HA's real trigger/template/blueprint semantics, restore across restarts, queued runs, the real PID.
- Not shown: real boot ordering (integrations load in parallel; here people exist before boot), real
  `person`/tracker behaviour, Zigbee timing, the physical TRV. Say so in the PR, and test those live.

## 2. Mutation testing: is the green suite worth anything?

```bash
scripts/mutate.py scripts/mutations/heating_policy.py --check   # every mutation still applies? (instant)
scripts/mutate.py scripts/mutations/heating_policy.py           # run all (~1 min each); needs a clean tree
scripts/mutate.py scripts/mutations/heating_policy.py 3 10 --tests tests/ha_mock/test_policy_review.py
```

Each mutation breaks one line of the config on purpose; the suite must go red. A **SURVIVED** mutation is
a behaviour nothing pins down: write the test, then re-run. Add mutations for new logic in a new file
under `scripts/mutations/`. Files are restored in a `finally`; still, run on a clean branch and check
`git status` afterwards.

## 3. Live: after the merge (WORKSPACE.md "After a merge: test it live")

Token (never print it, never write it to the repo; the Secrets server only hands it over encrypted):

```bash
scripts/live_keygen.sh                       # prints a public key block + fingerprint
#   -> call mcp__Secrets__get_ha_token with that block as armored_public_key; check the returned
#      recipient_fingerprint matches; then paste its `ciphertext` (JSON \n escapes are fine):
scripts/live_store_ciphertext.sh <<'EOF'
...ciphertext...
EOF
scripts/ha_live.py check                     # decrypts in memory, calls the API
...
scripts/live_cleanup.sh                      # delete the key and ciphertext when finished
```

Then:
- **Read first**: `ha_live.py states climate.`, `get ENTITY`. Confirm nothing moved or blinked after the
  restart before simulating anything. Wait: the instance is slow for a few minutes after a restart.
- **Orphans** (entities left behind after YAML was removed): `ha_live.py orphans` lists
  `unavailable`+`restored` entities; `orphans --remove [ENTITY...]` removes them from the registry,
  re-checking each is still an orphan. Do this only after the new config is verified.
- **Simulate**: use `live_testkit.Run` (snapshot, checks, restore in a `finally`, proof of exact restore).
  `scripts/live_test_heating_policy.py` is the worked example (14 checks; refuses to run unless Gaby is
  home and Charles is away; `--force` to override). Calls made through `ha_live` carry a *user* context,
  like the dashboard, so by-hand rules can be driven for real.

Safety rules (each was learned the hard way):
- **Never spoof `binary_sensor.anyone_home`** (or the people behind it) on the live box: it arms "Vacuum when
  everyone leaves" (a 20 h `last_triggered` guard, so a spoofed trip blocks the real run) and "Turn off all
  lights when everyone leaves". Test presence rules on the mock.
- Check who is actually home before touching any presence entity.
- Do not hand-toggle a PID climate to "fix" something: a by-hand off sets the room's switched-off switch.
- Snapshot first, restore in a `finally`, diff against the snapshot, report PASS/FAIL honestly, and say
  what was not exercised.

## Gotchas collected while building this

- A `for:` **state trigger never fires when the entity is already in that state at HA start**; use a template
  trigger on `last_changed`, or a template sensor with `delay_on`.
- Trigger-based template entities restore from **extra stored data**, not just state. A restart test that
  restores only `State` objects loses them (the harness restores through HA's own store, via JSON).
- `async_block_till_done` waits **in real time** for an automation sitting in a `delay`: advance the clock
  with `settle()` first. A 30 s delay once made the whole suite hang.
- Anything that fires `person.*` changes **during boot** (real HA does, the mock does not) can give a new
  trigger-based sensor its first value before dependent sensors exist. Expect a one-off blip on first deploy.
- A fixture that builds an "old world" with the NEW config will have the new automations quietly repair it.
  Switch them off while constructing the old state.
- Test assertions can be wrong, not just the code: read the failure before changing the config.
- The auto-mode classifier blocks `git push --force`. A branch whose PR was squash-merged can be pushed
  normally after `git merge -s ours origin/<old tip>`.
