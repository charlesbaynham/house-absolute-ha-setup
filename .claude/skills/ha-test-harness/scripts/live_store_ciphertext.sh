#!/usr/bin/env bash
# Step 2: store the ciphertext the Secrets server returned, and prove it decrypts.
#
#   live_store_ciphertext.sh <<'EOF'
#   -----BEGIN PGP MESSAGE-----
#   ...
#   -----END PGP MESSAGE-----
#   EOF
#
# The ciphertext is only decryptable with the ephemeral key from live_keygen.sh. The tool result is
# JSON, so its newlines arrive as "\n" escapes: this script accepts that form too. A single mistyped
# character fails the armour checksum, so a transcription error shows up here ("CRC error"), not later
# as a mysterious 401. The decrypted token is checked for non-emptiness and NEVER printed.
set -euo pipefail

DIR="${HA_LIVE_DIR:-/tmp/ha-live}"
export GNUPGHOME="$DIR/gnupg"
[ -d "$GNUPGHOME" ] || { echo "run live_keygen.sh first" >&2; exit 1; }

# turn literal \n sequences (from a JSON string) into newlines; leave real newlines alone
sed 's/\\n/\n/g' > "$DIR/ct.asc"
chmod 600 "$DIR/ct.asc"

if ! out="$(gpg --batch --quiet -d "$DIR/ct.asc" 2>&1 >/dev/null)"; then
  echo "decrypt FAILED: $out" >&2
  echo "(a 'CRC error' means a character was mistyped; copy the ciphertext again)" >&2
  rm -f "$DIR/ct.asc"
  exit 1
fi
if [ -z "$(gpg --batch --quiet -d "$DIR/ct.asc" 2>/dev/null)" ]; then
  echo "decrypted to an empty value" >&2
  exit 1
fi
echo "ciphertext stored and decrypts ($DIR/ct.asc). Next: ha_live.py check"
