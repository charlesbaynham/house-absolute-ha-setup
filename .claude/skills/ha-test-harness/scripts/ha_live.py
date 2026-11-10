#!/usr/bin/env python3
"""Client for the LIVE Home Assistant, for read-only checks and post-merge simulations.

Use as a library (`sys.path.insert(0, ".../scripts"); import ha_live as ha`) or from the shell:

    ha_live.py check                         token decrypts and the API answers
    ha_live.py version                       the live HA core version (keep the mock in step with it)
    ha_live.py states [PREFIX ...]           compact listing; PREFIX filters entity ids
    ha_live.py get ENTITY                    one state with its attributes (JSON)
    ha_live.py call DOMAIN SERVICE [JSON]    call a service, e.g. call input_boolean turn_on '{"entity_id": "..."}'
    ha_live.py orphans                       entities that are `unavailable` AND `restored` (left over after a
                                             config change); lists only
    ha_live.py orphans --remove [ENTITY ...] remove them (all of them, or just those named) from the entity
                                             registry. Each is re-checked to still be an orphan first.

The token comes from the ephemeral key + ciphertext set up by live_keygen.sh / live_store_ciphertext.sh
(in $HA_LIVE_DIR, default /tmp/ha-live). It is decrypted into memory per run, never printed, never written.
Calls retry (the instance can be slow right after a restart). Registry removal needs a websocket:
`aiohttp` is used, and if it is not installed this script re-runs itself with the mock-house venv's Python.

Service calls made through here carry a USER context (the token's user), exactly like the dashboard or
the app. Automations' own calls do not. Rules that depend on that distinction can be driven for real.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("HA_URL", "https://automation.houseabsolute.co.uk")
DIR = os.environ.get("HA_LIVE_DIR", "/tmp/ha-live")
_TOKEN = None


def token() -> str:
    global _TOKEN
    if _TOKEN is None:
        ct = os.path.join(DIR, "ct.asc")
        if not os.path.exists(ct):
            sys.exit("no ciphertext: run live_keygen.sh, call the Secrets tool, then live_store_ciphertext.sh")
        p = subprocess.run(["gpg", "--batch", "--quiet", "-d", ct], capture_output=True,
                           env={**os.environ, "GNUPGHOME": os.path.join(DIR, "gnupg")})
        _TOKEN = p.stdout.decode().strip()
        if not _TOKEN:
            sys.exit("could not decrypt the token (wrong key? re-run the keygen/ciphertext steps)")
    return _TOKEN


def call(method: str, path: str, body=None, tries: int = 4, timeout: int = 90):
    """REST call with retries. Returns parsed JSON (or None for an empty body)."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                BASE + path, method=method,
                data=None if body is None else json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as e:
            if e.code < 500:  # 4xx will not get better by retrying
                raise
            last = e
        except Exception as e:  # timeouts / resets while HA is restarting
            last = e
        time.sleep(5)
    raise last


def st(entity_id: str) -> dict:
    return call("GET", "/api/states/" + entity_id)


def svc(domain: str, service: str, data: dict | None = None):
    return call("POST", f"/api/services/{domain}/{service}", data or {})


def all_states() -> list:
    return call("GET", "/api/states")


def orphans() -> list:
    return [s for s in all_states()
            if s["state"] == "unavailable" and s.get("attributes", {}).get("restored")]


def registry_remove(entity_ids: list[str]) -> None:
    """Remove entities from the entity registry over the websocket API (orphans only)."""
    try:
        import asyncio
        import aiohttp
    except ImportError:
        venv_py = os.path.join(os.environ.get("HAMOCK_DIR", "/tmp/hamock"), "venv", "bin", "python")
        if os.path.exists(venv_py) and sys.executable != venv_py:
            os.execv(venv_py, [venv_py] + sys.argv)
        sys.exit("aiohttp is needed for registry removal: run setup_mock.sh (its venv has it)")

    async def run():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(BASE.replace("http", "ws", 1) + "/api/websocket", timeout=60) as ws:
                await ws.receive_json()
                await ws.send_json({"type": "auth", "access_token": token()})
                if (await ws.receive_json())["type"] != "auth_ok":
                    sys.exit("websocket auth failed")
                for n, e in enumerate(entity_ids, 1):
                    cur = st(e)  # safety: never remove something that is alive
                    if cur["state"] != "unavailable" or not cur["attributes"].get("restored"):
                        print(f"SKIP (not an orphan): {e} is {cur['state']}")
                        continue
                    await ws.send_json({"id": n, "type": "config/entity_registry/remove", "entity_id": e})
                    r = await ws.receive_json()
                    print(("removed  " if r.get("success") else "FAILED   ") + e, "" if r.get("success") else r.get("error"))

    asyncio.run(run())


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        cfg = call("GET", "/api/config")
        print(f"ok: Home Assistant {cfg['version']}, {len(all_states())} entities")
    elif cmd == "version":
        print(call("GET", "/api/config")["version"])
    elif cmd == "states":
        for s in sorted(all_states(), key=lambda x: x["entity_id"]):
            if not rest or any(s["entity_id"].startswith(p) for p in rest):
                print(f"{s['entity_id']:<60} {s['state']}")
    elif cmd == "get":
        print(json.dumps(st(rest[0]), indent=2))
    elif cmd == "call":
        print(json.dumps(svc(rest[0], rest[1], json.loads(rest[2]) if len(rest) > 2 else None), indent=2))
    elif cmd == "orphans":
        found = orphans()
        if "--remove" in rest:
            named = [a for a in rest if a != "--remove"]
            registry_remove(named or [s["entity_id"] for s in found])
        else:
            for s in found:
                print(s["entity_id"])
            print(f"{len(found)} orphan(s). Re-run with --remove to delete them from the registry.")
    else:
        print(f"unknown command: {cmd}\n", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
