#!/usr/bin/env bash
# Run the mock-house tests from the repo root with the venv that setup_mock.sh built.
#
#   run_mock_tests.sh                       the whole suite (about 70 s)
#   run_mock_tests.sh -k restart -x         any pytest arguments are passed through
#   run_mock_tests.sh tests/ha_mock/test_policy_presence.py
#
# Noise filter: the HA test plugin prints a "Lingering timer" warning per timer at teardown
# (the real PID thermostat keeps a keep-alive timer). They are expected and hidden here.
set -uo pipefail

DIR="${HAMOCK_DIR:-/tmp/hamock}"
PYTEST="$DIR/venv/bin/pytest"
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

if [ ! -x "$PYTEST" ]; then
  echo "no venv at $DIR: run $(dirname "$0")/setup_mock.sh first" >&2
  exit 1
fi

cd "$ROOT"
args=("$@")
if [ ${#args[@]} -eq 0 ] || [[ "${args[0]}" == -* ]]; then
  args=(tests/ha_mock "${args[@]}")
fi

"$PYTEST" "${args[@]}" -p no:cacheprovider 2>&1 | grep -v "Lingering timer"
exit "${PIPESTATUS[0]}"
