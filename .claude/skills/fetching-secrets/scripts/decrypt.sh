#!/usr/bin/env bash
# Verifies a Secret Server response was encrypted to OUR ephemeral key, then
# decrypts it to stdout. Pipe this straight into whatever consumes the
# secret (ssh-add, a variable assignment, another host over ssh) — never
# redirect it to a file or let it stand alone where its output becomes a
# tool result.
#
# Usage: decrypt.sh <ciphertext-file> <expected-recipient-fingerprint>
#
# <expected-recipient-fingerprint> is the recipient_fingerprint field from
# the get_<secret> tool's response. Refuses to decrypt if it doesn't match
# a key in the ephemeral keyring minted by mint-key.sh.

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: decrypt.sh <ciphertext-file> <expected-recipient-fingerprint>" >&2
  exit 2
fi

CIPHERTEXT_FILE="$1"
EXPECTED_FPR="$2"
PTR_FILE="${AGENT_GNUPGHOME_PTR:-/tmp/agent-secrets-gnupghome}"

if [ ! -f "$PTR_FILE" ]; then
  echo "no ephemeral key found — run mint-key.sh first" >&2
  exit 1
fi

GNUPGHOME="$(cat "$PTR_FILE")"
export GNUPGHOME

MATCH="$(gpg --with-colons --list-keys | grep -c "^fpr:::::::::${EXPECTED_FPR}:" || true)"
if [ "$MATCH" -ne 1 ]; then
  echo "FINGERPRINT MISMATCH: $EXPECTED_FPR is not our ephemeral key — refusing to decrypt" >&2
  exit 1
fi

gpg --quiet --batch --decrypt "$CIPHERTEXT_FILE"
