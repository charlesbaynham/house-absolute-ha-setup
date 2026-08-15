---
name: round-robin
description: >
  Play a TTS announcement around the house speakers one at a time, at maximum
  volume, then restore the original volumes.

  TRIGGER THIS SKILL WHEN:
  - The user wants something announced, broadcast, or played "around the house",
    "on the speakers", "on every speaker", or "one speaker at a time"
  - The user asks for a round robin / lap / loop of an announcement
  - The user wants to prank, page, or get the attention of someone in the house
  - Editing this skill, or changing the announcement volume/restore behaviour
metadata:
  version: 1
---

# Round Robin Announcements

## Purpose

Send a text-to-speech message hopping from speaker to speaker, one at a time,
for a number of laps around the house. Because it moves rather than playing
everywhere at once, it reads as a voice chasing someone through the house —
that travelling effect is the entire point, so never collapse it into a
simultaneous broadcast.

The announcement plays at **maximum volume**, and the speakers' original volumes
are **restored afterwards**.

## How to run it

```bash
python3 .claude/skills/round-robin/scripts/round_robin_announce.py \
  "your message here" --language es --rounds 3
```

Useful flags:

| Flag | Default | Notes |
| --- | --- | --- |
| `--rounds` | 3 | Laps around the house |
| `--language` | engine default | TTS language override, e.g. `es` |
| `--gap` | 6.0 | Seconds between speakers |
| `--volume` | 1.0 | 1.0 is maximum |
| `--speakers` | auto-discovered | Comma-separated entity_ids to override order |
| `--dry-run` | off | Print the plan and send nothing |

`--dry-run` is the way to check the speaker list and message without making a
sound. Use it whenever you want to confirm the setup is right but the moment
isn't right to actually fire.

The script needs `HA_TOKEN` in the environment. Never write that token into a
file in this repo — `gitsync.sh` runs `git add .` across the whole `/config`
directory and would commit and push it.

## Confirm before firing

This is loud, disruptive, aimed at whoever is in the house, and impossible to
take back once it has played. Before running it, make sure you actually have a
green light for *this* message at *this* moment. A user who says "record this
protocol", "set it up", or "for next time" is asking you to prepare it, not to
fire it — prepare it and stop. If in doubt, run `--dry-run` and show them the
plan.

## The protocol

The script does all of this; the sequence is written out so the reasoning
survives if it ever needs changing.

1. **Discover the speakers.** Any `media_player.*` with `device_class: speaker`,
   excluding the group entity (see below). Currently:
   `media_player.bedroom_speaker`, `media_player.gaby_speaker`,
   `media_player.living_room_speaker`. Discovery sorts alphabetically so runs are
   repeatable, which is not the same as the physical layout of the house. If the
   route matters — starting wherever the person actually is, say — pass the order
   you want with `--speakers`.
2. **Record every speaker's current `volume_level`.** These genuinely differ
   from each other — they have been seen at 0.6, 0.5 and 0.3 — so there is no
   single "normal" level to reset to afterwards. Capture per speaker.
3. **Set every speaker to maximum (1.0).** Do this to all of them up front, not
   per-hop, so the first speaker isn't quieter than the rest.
4. **Cycle the message**, one speaker per hop, `--gap` seconds apart, for
   `--rounds` laps. The gap keeps the hops from overlapping: Google's TTS takes
   a beat to fetch and the Chromecast targets take a moment to wake, so a short
   phrase still needs a few seconds of headroom to land cleanly.
5. **Restore the recorded volumes.** This runs from a `finally` block, so it
   happens even if a service call fails or the run is interrupted. Speakers left
   pinned at 1.0 is the one failure mode that really matters here — the next
   thing to use them will be deafening.

## Things that will bite you

**The TTS engine is English.** `tts.google_translate_en_com` is the only working
engine (`tts.piper` is `unavailable`). Given Spanish text without
`--language es`, it reads the letters as if they were English and produces
gibberish. Any time the message isn't English, pass `--language`.

**`media_player.all_speakers` is a group, not a speaker.** It contains the other
three. Announcing to it fires everything simultaneously and destroys the
travelling effect, so the script filters it out via `GROUP_ENTITIES`. If a new
speaker group is ever added, add it to that set.

**Speakers sitting at `off` are fine.** They are Chromecast targets and wake
themselves when TTS is cast to them; they return to `idle` afterwards. `off` in
the state list is not a reason to skip one or to power it on first.

**HTTP 200 doesn't prove it played.** The service call returns 200 once accepted.
To confirm audio actually reached the speakers, re-read their states afterwards
and check each one's `media_content_id` points at a fresh
`/api/tts_proxy/*.mp3` with a timestamp matching the run.

## Verifying afterwards

```bash
curl -sS -H "Authorization: Bearer $HA_TOKEN" \
  https://automation.houseabsolute.co.uk/api/states \
  | python3 -c "
import json,sys
for e in json.load(sys.stdin):
    if e['attributes'].get('device_class')=='speaker':
        print(e['entity_id'], e['state'],
              e['attributes'].get('volume_level'),
              e['attributes'].get('media_content_id'))
"
```

Check two things: the `media_content_id` values are fresh TTS URLs, and the
`volume_level` values match what they were before the run.
