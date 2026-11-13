#!/usr/bin/env bash
# Mints an ephemeral, passphrase-less GPG keypair for receiving one Secret
# Server response. Prints the armored public key on stdout — paste it
# straight into a get_<secret> tool call's armored_public_key argument.
#
# GNUPGHOME lives under /tmp, deliberately NOT the session scratchpad:
# gpg-agent's UNIX socket blows past the ~108-char sun_path limit on a
# scratchpad-length path (see SKILL.md). Its path is recorded in $PTR_FILE
# so later, separate Bash calls — which don't inherit this shell's env —
# can pick the same keyring back up via decrypt.sh instead of re-minting.
#
# Usage: mint-key.sh
# Output: armored public key on stdout; fingerprint and pointer path on stderr.

set -euo pipefail

PTR_FILE="${AGENT_GNUPGHOME_PTR:-/tmp/agent-secrets-gnupghome}"

GNUPGHOME="$(mktemp -d /tmp/ag.XXXXXX)"
chmod 700 "$GNUPGHOME"
export GNUPGHOME

gpg --batch --pinentry-mode loopback --passphrase '' \
    --quick-generate-key "Ephemeral Agent <agent@localhost>" default default 0 \
    >/dev/null 2>&1

echo "$GNUPGHOME" > "$PTR_FILE"

FPR="$(gpg --with-colons --list-keys agent@localhost | awk -F: '/^fpr:/ {print $10; exit}')"
echo "fingerprint: $FPR" >&2
echo "GNUPGHOME recorded at: $PTR_FILE" >&2

gpg --armor --export agent@localhost
