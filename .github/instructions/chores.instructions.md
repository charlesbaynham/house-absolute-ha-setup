---
applyTo: "**chore**"
---

# Chore Mode Configuration - AI Agent Guide

## Purpose
Chore Mode tracks household chore time for Charles and Gaby, controlled by a dual-button Aqara switch. It logs minutes while active, provides timeout logic, and offers an "extended" mode with periodic reminders. This guidance explains how it works and how to safely modify or extend it.

## Core Concepts
- **People**: Charles and Gaby.
- **Control Device**: Aqara switch `device_id: eea20367040d6e9ad92eee3f0dc0ede2`.
  - `single_left`: Start/renew Charles' session; if extended mode is ON, single press turns it OFF.
  - `single_right`: Start/renew Gaby's session; if extended mode is ON, single press turns it OFF.
  - `double_left`: Start Charles' extended chore mode.
  - `double_right`: Start Gaby's extended chore mode.
- **Regular Mode**: Times out after `input_number.chore_timeout_minutes` of inactivity.
- **Extended Mode**: Times out after `input_number.extended_chore_timeout_hours` (default 6 hours); plays a reminder TTS every 5 minutes; single press turns it OFF. If it times out, ALL minutes from that session are removed from the counter.

## Entities and Structure
All configuration lives in `packages/chore_tracking.yaml` and the dashboard view in `dashboards/chore-tracking.yaml`.

### Helpers
- `input_boolean.chore_mode_charles`
- `input_boolean.chore_mode_gaby`
- `input_boolean.extended_chore_mode_charles`
- `input_boolean.extended_chore_mode_gaby`
- `input_number.chore_timeout_minutes` (default 5)
- `input_number.extended_chore_timeout_hours` (default 6) — configurable timeout for extended mode
- `input_number.chore_minutes_charles`
- `input_number.chore_minutes_gaby`
- `input_number.extended_session_minutes_charles` — tracks minutes in current extended session
- `input_number.extended_session_minutes_gaby` — tracks minutes in current extended session
- `input_datetime.chore_last_activity_charles`
- `input_datetime.chore_last_activity_gaby`
- `input_datetime.extended_chore_start_charles` — timestamp when extended mode started
- `input_datetime.extended_chore_start_gaby` — timestamp when extended mode started

### Template Sensors
- `sensor.chore_minutes_charles`, `sensor.chore_minutes_gaby` — expose minutes for `utility_meter`.
- `sensor.chore_weekly_leader` — shows weekly leader based on utility meters.
- `sensor.charles_last_activity_relative`, `sensor.gaby_last_activity_relative` — human-readable last activity.

### Utility Meters
Create rolling aggregates for minutes:
- Daily: `sensor.chore_minutes_charles_daily`, `sensor.chore_minutes_gaby_daily`
- Weekly: `sensor.chore_minutes_charles_weekly`, `sensor.chore_minutes_gaby_weekly`
- Monthly: `sensor.chore_minutes_charles_monthly`, `sensor.chore_minutes_gaby_monthly`
- Yearly: `sensor.chore_minutes_charles_yearly`, `sensor.chore_minutes_gaby_yearly`
- Quick (debug, 15-minute cycle): `sensor.chore_minutes_charles_quick`, `sensor.chore_minutes_gaby_quick`

### Automations (summary)
- Button press handlers for start/renew and extended mode (mapped to MQTT device actions).
- Accumulators: add 1 minute per minute while `chore_mode_*` is ON; also track extended session minutes.
- Timeout: turn OFF `chore_mode_*` after configured inactivity unless extended mode is ON.
- Timeout warnings: flash lights 1 minute before timeout (when not extended).
- Extended mode announcements and reminders via TTS every 5 minutes.
- Extended mode timeout: after 6 hours, turn OFF extended mode and subtract all session minutes from total.
- Extended mode timeout warning: announce 30 minutes before extended mode times out.
- Session counter reset: when extended mode is turned off, reset the session minutes counter.

### Dashboard
`dashboards/chore-tracking.yaml` renders gauges and entities:
- Status and extended mode toggles per person.
- Time period displays: quarter-hourly (quick), daily, weekly, monthly, yearly, and all-time total meters.
- Last activity relative.
- Weekly leader banner when not tied.
- Mini graph card for quick meters.

## Editing Guidelines
- Use 2-space indentation and standard Home Assistant YAML conventions.
- Do not change the Aqara switch `device_id` unless replacing the physical device.
- When adding a new person, mirror the complete set of helpers, sensors, meters, and automations; keep naming consistent (`<name>` in lowercase for entity ids, proper case for display names).
- Accumulator cadence is 1 minute; if changing, adjust all related logic (accumulator, timeout templates, reminder intervals) to remain consistent.
- Extended mode reminder uses `media_player.living_room_speaker` and `tts.google_translate_en_com`. If changing TTS or speaker, update all extended-mode announcement/reminder automations consistently.
- Utility meters use offsets (4 hours, weeks offset 6 days + 4 hours) to align with household reporting; modify carefully and keep both persons aligned.
- Do not edit Zigbee2MQTT device lists (`zigbee2mqtt/configuration.yaml`); the chore system only consumes the action events via device triggers.

## Common Extensions
- Add a new person: copy-paste blocks for helpers, template sensors, utility meters, and automations; replace names; add to dashboard view.
- Change timeout duration UI: adjust `input_number.chore_timeout_minutes` or `input_number.extended_chore_timeout_hours` ranges or defaults.
- Add visual/lighting feedback: re-use `script.flash_kitchen_surface_lights` or add variants; call from existing automations.
- Modify reminder frequency: update `triggers: time_pattern minutes: /5` and wording.

## Scripts
- `script.chore_initialize_yearly_meters`: One-time initialization script to copy current monthly meter values to the yearly meters. Run this manually via the Home Assistant UI when first setting up yearly meters to preserve existing totals.

## Safety Checks
- Ensure all `entity_id` references exist after changes; mismatches will break automations.
- Validate templates after edits for `none`/`unavailable` handling (pattern used in file avoids errors).
- Keep extended-mode ON/OFF logic symmetrical across both people to avoid inconsistent behavior.
- Ensure that the instructions at `.github/instructions/chores.instructions.md` are updated if significant changes are made to functionality or entities.

## Known Design Decisions
- `input_number.chore_minutes_*` maintains all-time totals that continuously accumulate; utility meters create rolling daily/weekly/monthly aggregates from these totals.
- Extended mode reminder is intentionally frequent to provide accountability; disable by turning OFF extended mode or editing the reminder automation.
- Extended mode timeout (configurable, default 6 hours) removes ALL session minutes to prevent accidental accumulation of thousands of minutes when left on by mistake.
- Session minutes are tracked separately during extended mode so they can be rolled back if timeout occurs.
- Manual deactivation of extended mode (via button or dashboard) keeps the minutes; only timeout removes them.
- Timeout duration is configurable via `input_number.extended_chore_timeout_hours` for flexibility.
