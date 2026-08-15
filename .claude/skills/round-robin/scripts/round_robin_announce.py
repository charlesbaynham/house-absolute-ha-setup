#!/usr/bin/env python3
"""Play a TTS announcement around the house speakers one at a time.

Captures each speaker's current volume, raises them all to maximum, cycles the
message speaker-by-speaker for N rounds, then puts the volumes back exactly as
they were. The restore runs from a `finally` block so an exception, a failed
service call or a Ctrl-C still hands the speakers back at their original levels
-- leaving them pinned at 1.0 is the one outcome that turns a joke into a
problem at 3am.

Reads the HA token from $HA_TOKEN. Never hardcode or write the token anywhere:
this repo is the live /config directory and gitsync.sh auto-commits it.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://automation.houseabsolute.co.uk"

# media_player.all_speakers is a *group* containing the three physical speakers.
# Announcing to it fires everything simultaneously, which is the opposite of a
# round robin, so it is excluded from discovery.
GROUP_ENTITIES = {"media_player.all_speakers"}


def api(base, token, path, payload=None, timeout=30):
    url = f"{base}/api/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body) if body.strip() else None


def discover_speakers(base, token):
    """Physical speakers, in a stable order, group entity excluded."""
    states = api(base, token, "states")
    found = []
    for e in states:
        eid = e["entity_id"]
        if not eid.startswith("media_player."):
            continue
        if eid in GROUP_ENTITIES:
            continue
        if e.get("attributes", {}).get("device_class") != "speaker":
            continue
        found.append(eid)
    return sorted(found)


def current_volumes(base, token, speakers):
    """Map entity_id -> volume_level, skipping any that don't report one.

    A speaker that is fully powered down may not expose volume_level. Recording
    nothing for it is correct: we then also skip restoring it, rather than
    inventing a level it never had.
    """
    states = {e["entity_id"]: e for e in api(base, token, "states")}
    vols = {}
    for s in speakers:
        v = states.get(s, {}).get("attributes", {}).get("volume_level")
        if v is not None:
            vols[s] = v
    return vols


def set_volume(base, token, entity, level):
    api(
        base,
        token,
        "services/media_player/volume_set",
        {"entity_id": entity, "volume_level": level},
    )


def speak(base, token, entity, message, tts_entity, language):
    payload = {
        "entity_id": tts_entity,
        "media_player_entity_id": entity,
        "message": message,
    }
    if language:
        payload["language"] = language
    api(base, token, "services/tts/speak", payload)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("message", help="Text to announce")
    p.add_argument("--rounds", type=int, default=3, help="Laps of the house (default 3)")
    p.add_argument(
        "--language",
        default=None,
        help="TTS language override, e.g. 'es'. The configured engine is "
        "English; without this, non-English text is read phonetically as "
        "English and comes out as gibberish.",
    )
    p.add_argument("--gap", type=float, default=6.0, help="Seconds between speakers (default 6)")
    p.add_argument("--volume", type=float, default=1.0, help="Announcement volume 0.0-1.0 (default 1.0 = max)")
    p.add_argument("--speakers", default=None, help="Comma-separated entity_ids, overriding discovery")
    p.add_argument("--tts-entity", default="tts.google_translate_en_com")
    p.add_argument("--base", default=os.environ.get("HA_BASE_URL", DEFAULT_BASE))
    p.add_argument("--dry-run", action="store_true", help="Show the plan, touch nothing")
    args = p.parse_args()

    token = os.environ.get("HA_TOKEN")
    if not token:
        sys.exit("HA_TOKEN is not set in the environment.")

    if args.speakers:
        speakers = [s.strip() for s in args.speakers.split(",") if s.strip()]
    else:
        speakers = discover_speakers(args.base, token)

    if not speakers:
        sys.exit("No speakers found. Pass --speakers explicitly.")

    print(f"Speakers ({len(speakers)}), in order:")
    for s in speakers:
        print(f"  - {s}")
    print(f"Message : {args.message!r}")
    print(f"Language: {args.language or '(engine default)'}")
    print(f"Rounds  : {args.rounds}   Gap: {args.gap}s   Volume: {args.volume}")

    if args.dry_run:
        print("\n--dry-run: nothing sent.")
        return

    original = current_volumes(args.base, token, speakers)
    print("\nOriginal volumes:")
    for s in speakers:
        print(f"  {s} = {original.get(s, '(not reported, will not restore)')}")

    try:
        for s in speakers:
            set_volume(args.base, token, s, args.volume)
        print(f"\nAll speakers set to {args.volume}.\n")

        for r in range(1, args.rounds + 1):
            for s in speakers:
                speak(args.base, token, s, args.message, args.tts_entity, args.language)
                print(f"{time.strftime('%H:%M:%S')}  round {r}/{args.rounds} -> {s}")
                time.sleep(args.gap)
    finally:
        # Runs even on failure or Ctrl-C: speakers must never be left at max.
        print("\nRestoring original volumes:")
        for s, v in original.items():
            try:
                set_volume(args.base, token, s, v)
                print(f"  {s} -> {v}")
            except (urllib.error.URLError, OSError) as exc:
                print(f"  !! {s} FAILED to restore to {v}: {exc}")
                print("     Set it back by hand before leaving this.")

    print("\nDone.")


if __name__ == "__main__":
    main()
