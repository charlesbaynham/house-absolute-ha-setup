"""Small kit for post-merge live simulations (WORKSPACE.md: "After a merge: test it live").

The pattern, which every live test should follow:

    from live_testkit import Run
    run = Run(snapshot_entities=[...])          # states AND selected attributes are recorded now
    with run:                                   # restore + report happen in a `finally`
        run.service("input_boolean", "turn_on", {"entity_id": "..."})
        run.check("it reacted", run.wait(lambda: run.state("climate.x") == "heat"))
        ...
    # leaving the block restores the snapshot (via `run.restore_steps`) and prints PASS/FAIL totals

Rules this encodes (learned the hard way, see SKILL.md):
  * snapshot first, restore in a finally, then prove the restore by diffing against the snapshot;
  * assert preconditions (who is home) before touching anything;
  * never spoof a presence entity casually: `binary_sensor.anyone_home` arms other automations.
"""
import sys
import time

import ha_live as ha


class Run:
    def __init__(self, snapshot_entities, attrs=("temperature",), restore_steps=None, settle=25):
        """snapshot_entities: entity ids whose state (+ `attrs`) are recorded and compared after.
        restore_steps: callable run in the finally (e.g. turn switches off, reset helper values)."""
        self.entities = list(snapshot_entities)
        self.attrs = attrs
        self.restore_steps = restore_steps
        self.settle = settle
        self.results = []
        self.before = {}

    # -- reading -----------------------------------------------------------------------
    def state(self, entity_id):
        return ha.st(entity_id)["state"]

    def attr(self, entity_id, name):
        return ha.st(entity_id)["attributes"].get(name)

    def snap(self):
        out = {}
        for e in self.entities:
            s = ha.st(e)
            out[e] = (s["state"],) + tuple(s["attributes"].get(a) for a in self.attrs)
        return out

    # -- acting ------------------------------------------------------------------------
    def service(self, domain, service, data=None):
        return ha.svc(domain, service, data)

    def wait(self, cond, timeout=40, step=2):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if cond():
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False

    # -- reporting ---------------------------------------------------------------------
    def check(self, name, ok, extra=""):
        self.results.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name, extra, flush=True)

    def __enter__(self):
        self.before = self.snap()
        print("BEFORE", self.before, flush=True)
        return self

    def __exit__(self, *exc):
        try:
            if self.restore_steps:
                self.restore_steps()
            time.sleep(self.settle)
            after = self.snap()
            diff = {e: (self.before[e], after[e]) for e in self.entities if self.before[e] != after[e]}
            print("RESTORED EXACTLY" if not diff else f"NOT RESTORED: {diff}", flush=True)
            self.results.append(not diff)
        finally:
            print(f"{sum(self.results)}/{len(self.results)} checks passed", flush=True)
        if exc[0] is not None:
            return False
        if not all(self.results):
            sys.exit(1)
        return False
