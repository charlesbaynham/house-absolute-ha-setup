---
name: ha-api-token
description: >
  How to obtain the Home Assistant long-lived access token (HA_TOKEN) from the Secrets MCP server
  and use it against the live HA REST API without leaking it.

  TRIGGER THIS SKILL WHEN:
  - `$HA_TOKEN` is unset and you need to query or call the live Home Assistant API
  - Verifying entity IDs / states on the live instance before or after editing YAML
  - The user says "get the HA token" / "use the secret server"
metadata:
  version: 1
---

# Getting the HA token from the Secrets server

The `Secrets` MCP server hands secrets over **encrypted to a PGP key you supply**. Never ask for or
print the plaintext. The token must not reach stdout, a tool result, a command argument, or any file
inside this repo (`gitsync.sh` auto-commits and pushes everything under `/config`).

Live API base URL: `https://automation.houseabsolute.co.uk` (the `10.0.1.2` address the tool mentions
is LAN-only and unreachable from cloud sessions).

## Steps

1. Load the tools: `ToolSearch` with `select:mcp__Secrets__get_ha_token,mcp__Secrets__secretserver_status`.
   (`secretserver_status` returns no secret values; `ha_token` should be listed under `seeded`.)

2. Mint an ephemeral keypair. **Use a short `GNUPGHOME`** (e.g. `mktemp -d /tmp/g.XXXX`) — the
   scratchpad path is too long for the gpg-agent unix socket ("No agent running"). Keep it outside the
   git tree.

   ```bash
   export GNUPGHOME=$(mktemp -d /tmp/g.XXXX); chmod 700 $GNUPGHOME
   gpg --batch --quiet --passphrase '' --quick-generate-key "ha-ephemeral <ha@local>" rsa3072 encr 1d
   gpg --list-keys --with-colons ha@local | awk -F: '/^fpr/{print $10; exit}'   # fingerprint
   gpg --armor --export ha@local                                                # public key
   ```

3. Call `mcp__Secrets__get_ha_token` with `armored_public_key` = the exported block. Check the returned
   `recipient_fingerprint` equals your fingerprint.

4. Save the returned `ciphertext` (it is only decryptable with the ephemeral key) into
   `$GNUPGHOME/ct.asc`, then decrypt **straight into the consumer**. `curl -H @-` reads headers from
   stdin, so the token never appears in argv:

   ```bash
   gpg --batch --quiet -d $GNUPGHOME/ct.asc 2>/dev/null \
     | { IFS= read -r t; printf 'Authorization: Bearer %s\n' "$t"; } \
     | curl -sS -H @- https://automation.houseabsolute.co.uk/api/states/<entity_id>
   ```

   Redirect `/api/states` (large) to a file under `$GNUPGHOME`, not the repo, and filter it with
   Python rather than printing it all. Service calls: add `-X POST -H 'Content-Type: application/json'
   -d '{...}'` to the same pipeline.

5. When finished, `rm -rf "$GNUPGHOME"`. Re-fetching takes one tool call.

## Rules

- Never `echo`/`cat`/`export` the decrypted token, and never write it to a file.
- Live API writes take effect immediately and bypass the repo; read-only checks are the normal use.
  Confirm with the user before calling services that change the house (heating, locks, etc.).
