#!/usr/bin/env bash
# Removes the ephemeral keyring created by mint-key.sh. Not required — the
# container is reclaimed at session end anyway — but tidy if a session
# mints more than one key and wants to drop an earlier one deliberately.
#
# Usage: cleanup.sh

set -euo pipefail

PTR_FILE="${AGENT_GNUPGHOME_PTR:-/tmp/agent-secrets-gnupghome}"

if [ -f "$PTR_FILE" ]; then
  GNUPGHOME="$(cat "$PTR_FILE")"
  rm -rf "$GNUPGHOME"
  rm -f "$PTR_FILE"
  echo "removed $GNUPGHOME" >&2
fi
