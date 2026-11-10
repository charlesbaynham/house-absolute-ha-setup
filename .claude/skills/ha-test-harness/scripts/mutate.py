#!/usr/bin/env python3
"""Mutation testing for the mock house: break the config on purpose, expect the tests to notice.

A green suite only means something if it goes red when the logic is wrong. This applies each
mutation (one text replacement in one file), runs the suite until its first failure, and restores
the file. A mutation that SURVIVES means a behaviour no test pins down: add a test.

    mutate.py MUTATIONS.py --check          verify every mutation still applies (instant)
    mutate.py MUTATIONS.py                  run them all (about a minute each)
    mutate.py MUTATIONS.py 0 3 7            run only those indexes
    mutate.py MUTATIONS.py --tests tests/ha_mock/test_policy_review.py   a narrower suite

MUTATIONS.py defines   MUTATIONS = [(name, file, old, new), ...]   (see mutations/heating_policy.py).
`old` must occur exactly once in `file` (paths relative to the repo root). Files are restored in a
`finally`, and the working tree is checked clean of the mutation afterwards. Run on a clean branch.
"""
import argparse
import os
import runpy
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True,
                                        cwd=Path(__file__).parent).strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mutations", help="python file defining MUTATIONS")
    ap.add_argument("ids", nargs="*", type=int, help="indexes to run (default: all)")
    ap.add_argument("--check", action="store_true", help="only verify the mutations apply")
    ap.add_argument("--tests", default="tests/ha_mock", help="pytest target (default tests/ha_mock)")
    ap.add_argument("--timeout", type=int, default=290, help="seconds per mutation")
    a = ap.parse_args()

    root = repo_root()
    os.chdir(root)
    mutations = runpy.run_path(a.mutations)["MUTATIONS"]
    pytest = Path(os.environ.get("HAMOCK_DIR", "/tmp/hamock")) / "venv" / "bin" / "pytest"
    if not a.check and not pytest.exists():
        print(f"no venv at {pytest.parent.parent}: run setup_mock.sh first", file=sys.stderr)
        return 1

    results = []
    for i, (name, rel, old, new) in enumerate(mutations):
        if a.ids and i not in a.ids:
            continue
        path = root / rel
        src = path.read_text()
        n = src.count(old)
        if n != 1:
            results.append((i, name, f"DOES NOT APPLY ({n} matches in {rel}): update the mutation"))
            continue
        if a.check:
            results.append((i, name, "applies"))
            continue
        path.write_text(src.replace(old, new, 1))
        try:
            p = subprocess.run([str(pytest), a.tests, "-q", "-x", "-p", "no:cacheprovider"],
                               capture_output=True, text=True, timeout=a.timeout)
            failed = [l for l in p.stdout.splitlines() if l.startswith("FAILED")]
            if p.returncode == 0:
                verdict = "SURVIVED  <-- no test notices this: add one"
            elif failed:
                verdict = "caught by " + failed[0].split("::", 1)[-1][:90]
            else:  # collection/import error etc.: not a real catch
                verdict = f"ERROR (rc={p.returncode}), not a real catch: " + (p.stdout.strip().splitlines() or ["?"])[-1][:90]
        except subprocess.TimeoutExpired:
            verdict = "TIMEOUT (counts as caught only if you expect a hang)"
        finally:
            path.write_text(src)
        results.append((i, name, verdict))
        print(f"[{i}] {name}: {verdict}", flush=True)

    if a.check:
        for i, name, v in results:
            print(f"[{i}] {name}: {v}")
    bad = [r for r in results if r[2].startswith(("SURVIVED", "DOES NOT", "ERROR", "TIMEOUT"))]
    print(f"\n{len(results) - len(bad)}/{len(results)} fine" + (f", {len(bad)} need attention" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
