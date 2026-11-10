#!/usr/bin/env bash
# Delete the ephemeral key, the stored ciphertext and any token cache. Run when the live work is done.
set -euo pipefail
DIR="${HA_LIVE_DIR:-/tmp/ha-live}"
gpgconf --kill gpg-agent 2>/dev/null || GNUPGHOME="$DIR/gnupg" gpgconf --kill gpg-agent 2>/dev/null || true
rm -rf "$DIR"
echo "removed $DIR"
