#!/usr/bin/env bash
# Set up the mock house: a real Home Assistant core in a Python 3.14 venv, plus the
# pytest helpers, so `tests/ha_mock` can run. Idempotent: safe to re-run, skips what exists.
#
#   setup_mock.sh [--ha-version 2026.10.0] [--dir /tmp/hamock] [--run]
#
# --ha-version  HA core to install. Keep it equal to the live instance
#               (`ha_live.py version` prints it). Default: $HA_VERSION or 2026.10.0.
# --dir         where the venv goes (default $HAMOCK_DIR or /tmp/hamock). Outside the repo
#               on purpose: gitsync commits everything under /config.
# --run         run the whole tests/ha_mock suite afterwards.
set -euo pipefail

HA_VERSION="${HA_VERSION:-2026.10.0}"
DIR="${HAMOCK_DIR:-/tmp/hamock}"
RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ha-version) HA_VERSION="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --run) RUN=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required (https://docs.astral.sh/uv/). Try: pip install uv" >&2
  exit 1
fi

export HAMOCK_DIR="$DIR"   # the run script and mutate.py read this
PY="$DIR/venv/bin/python"

# 1. Python 3.14 (HA 2026.10 needs it; uv fetches a standalone build, no root needed)
uv python install 3.14 >/dev/null

# 2. venv
if [ ! -x "$PY" ]; then
  mkdir -p "$DIR"
  uv venv --python 3.14 "$DIR/venv" -q
  echo "created venv: $DIR/venv"
fi

# 3. HA core + the test helpers (the helper package pins compatible versions of everything)
have="$("$PY" -c 'import homeassistant.const as c; print(c.__version__)' 2>/dev/null || true)"
if [ "$have" != "$HA_VERSION" ] || ! "$PY" -c 'import pytest_homeassistant_custom_component' 2>/dev/null; then
  echo "installing homeassistant==$HA_VERSION (+ pytest-homeassistant-custom-component) ..."
  uv pip install --python "$PY" -q "homeassistant==$HA_VERSION" pytest-homeassistant-custom-component
fi

got="$("$PY" -c 'import homeassistant.const as c; print(c.__version__)')"
if [ "$got" != "$HA_VERSION" ]; then
  echo "WARNING: installed Home Assistant $got, wanted $HA_VERSION (the test helper package may" >&2
  echo "         pin a different core). The mock then differs from the live box." >&2
fi
echo "mock house ready: Home Assistant $got in $DIR/venv"
echo "run:  $(dirname "$0")/run_mock_tests.sh        (or: $DIR/venv/bin/pytest tests/ha_mock)"

if [ "$RUN" = 1 ]; then
  exec "$(dirname "$0")/run_mock_tests.sh"
fi
