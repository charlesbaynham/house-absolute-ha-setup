#!/usr/bin/env bash
# Step 1 of getting the live HA token: mint an ephemeral PGP keypair.
#
#   live_keygen.sh
#
# Prints the PUBLIC key block and its fingerprint. Pass the block as `armored_public_key` to the
# `mcp__Secrets__get_ha_token` tool, check the returned `recipient_fingerprint` equals the one
# printed here, then pipe the returned `ciphertext` into live_store_ciphertext.sh.
#
# State lives in $HA_LIVE_DIR (default /tmp/ha-live), outside the repo: gitsync.sh commits and pushes
# everything under /config, and there is no secret scanning. Remove it when done: live_cleanup.sh.
# (A short path matters: gpg-agent's unix socket path has a length limit.)
set -euo pipefail

DIR="${HA_LIVE_DIR:-/tmp/ha-live}"
export GNUPGHOME="$DIR/gnupg"

rm -rf "$DIR"
mkdir -p "$GNUPGHOME"
chmod 700 "$DIR" "$GNUPGHOME"

gpg --batch --quiet --passphrase '' --quick-generate-key "ha-ephemeral <ha@local>" rsa3072 encr 1d 2>/dev/null

echo "fingerprint: $(gpg --list-keys --with-colons ha@local | awk -F: '/^fpr/{print $10; exit}')"
echo "--- armored_public_key (copy the whole block) ---"
gpg --armor --export ha@local
