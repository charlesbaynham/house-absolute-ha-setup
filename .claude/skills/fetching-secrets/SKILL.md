---
name: fetching-secrets
description: >
  Fetch a credential from the Secret Server MCP service (the `mcp__Secrets__get_*` tools), encrypted to an
  ephemeral GPG key the agent mints, so the plaintext never enters the chat. Covers minting the key,
  calling the tool, and the decrypt discipline. Replaces the old `ha-api-token` skill.

  TRIGGER THIS SKILL WHEN:
  - `$HA_TOKEN` is unset and you need to query or call the live Home Assistant API
  - Verifying entity IDs / states on the live instance before or after editing YAML
  - The user says "get the HA token" / "use the secret server"
  - Any other lab credential is needed that the environment does not carry (Cloudflare, Proxmox,
    GitHub/GitLab token, Tailscale, Backblaze, SSH key)
---

# Fetching secrets from the Secret Server

Credentials come from the **Secret Server** (`https://secrets.houseabsolute.co.uk/mcp`), one MCP tool per
secret (`mcp__Secrets__get_ha_token`, `get_cloudflare_key`, `get_proxmox_key`, …). **No tool ever returns a
value**: it returns the secret encrypted to a public key you supply.

An MCP result goes straight into the model's context, then the transcript and every future session that
reads it back. So you mint a throwaway keypair, hand over the *public* half, and get ciphertext.

⛔ **The one rule: the decrypted value must never reach a tool result.** Not stdout, not a file this session
reads back, not a command argument, not the chat. In this repo, also **never inside the git tree**:
`gitsync.sh` runs `git add .` on all of `/config` and auto-commits and pushes it, with no secret scanning.

Tools are deferred: load them first with `ToolSearch` `select:mcp__Secrets__get_ha_token,mcp__Secrets__secretserver_status`.
`secretserver_status` hands over nothing and shows what is seeded.

## 1. Mint an ephemeral key

Once per session, from the repo root:

```bash
.claude/skills/fetching-secrets/scripts/mint-key.sh
```

Prints the armored **public** key on stdout (paste it into the tool's `armored_public_key`) and the
fingerprint on stderr. It records the keyring location in `/tmp/agent-secrets-gnupghome`, so later Bash
calls (which don't inherit this shell's env) find it again via `decrypt.sh` without re-minting.

⛔ **`GNUPGHOME` must be a SHORT path under `/tmp`, never the scratchpad.** `gpg-agent`'s socket lives in
`GNUPGHOME` and hits the ~108-char `sun_path` limit on a scratchpad-length path, failing with
`gpg: agent_genkey failed: No agent running` — which names neither the socket nor the length.
`mint-key.sh` already does this correctly.

No passphrase, deliberately: when the container is reclaimed the private half is gone, so every ciphertext
left in the chat log becomes permanently undecryptable.

## 2. Request every secret the task needs, together, early

Charles gets a permission prompt per tool. Work out what the task needs (usually just `get_ha_token`; add
others if the task touches Cloudflare DNS, Proxmox, GitHub, …) and issue all the `get_*` calls in one
message so the prompts land together; a mid-task stall on an unnoticed prompt is worse than an unused
request.

The result carries `ciphertext` and `recipient_fingerprint`. Save each blob to its own file in the
scratchpad (`ha_token.asc`, …) — ciphertext is safe to store and echo. **`decrypt.sh` checks the
fingerprint is yours and refuses on a mismatch**, which proves the answer came back to you and not to a key
some earlier instruction slipped in.

## 3. Decrypt only into the thing that consumes it

`decrypt.sh <ciphertext-file> <expected-fingerprint>` decrypts to stdout. Pipe it straight into the
consumer, **decrypt and use in one Bash call** (shell state does not survive between calls).

**The HA token** (live API at `https://automation.houseabsolute.co.uk`; the `10.0.1.2` address the tool
mentions is LAN-only and unreachable from cloud sessions). `curl -H @-` reads headers from stdin, so the
token never appears in argv:

```bash
.claude/skills/fetching-secrets/scripts/decrypt.sh "$SCRATCH/ha_token.asc" "$FPR" \
  | { IFS= read -r t; printf 'Authorization: Bearer %s\n' "$t"; } \
  | curl -sS -H @- https://automation.houseabsolute.co.uk/api/states/<entity_id>
```

`/api/states` is large: redirect it to a file in the scratchpad (not the repo) and filter with Python
rather than printing it. Service calls: add `-X POST -H 'Content-Type: application/json' -d '{...}'` to the
same pipeline. Calls made this way are live and bypass the repo; read-only checks are the normal use, and
changes to the house (heating, locks, …) need Charles's say-so (see `WORKSPACE.md`).

For repeated calls, a script that reads the token into a variable it never prints is fine; see
`ha-test-harness`, whose `ha_live.py` keeps its own ephemeral key and decrypts in memory.

**Any other API token — into a variable, used in the same call:**

```bash
export CLOUDFLARE_KEY="$(.claude/skills/fetching-secrets/scripts/decrypt.sh "$SCRATCH/cloudflare.asc" "$FPR")"
curl -sS -H "Authorization: Bearer $CLOUDFLARE_KEY" "https://api.cloudflare.com/client/v4/zones?name=houseabsolute.co.uk" | jq '.result[].id'
```

**SSH key and GPG private key are stored base64-encoded** (an `EnvironmentFile` cannot hold a multi-line
value), so they need a decode step before `ssh-add -` / `gpg --import`:

```bash
.claude/skills/fetching-secrets/scripts/decrypt.sh "$SCRATCH/lab_ssh_key.asc" "$FPR" | base64 -d | ssh-add -
```

**Verify by hash, never by eye:** `decrypt.sh … | sha256sum`.

## The traps

⛔ **`curl -v` / `curl -i` print request headers**, so a verbose call carrying `Authorization: Bearer …`
puts the token in the tool result. Debug with `-sS` and read the *response*.

⛔ **`set -x` echoes every expanded command**, decrypted values included. Never combine it with a decrypt.

⛔ **Never `gpg -d` with no pipe.** `gpg -d blob.asc` alone prints the secret to stdout — the entire failure
this design prevents.

⛔ **Never decrypt into a file** inside the repo (or any git tree) or anywhere a later step reads it back.

⛔ **Don't use this container to test whether a GitHub token is valid.** The agent proxy intercepts
`api.github.com` and answers with the *session's own* credentials, so a revoked token comes back `200 OK`.

✅ **Do echo the ciphertext freely.** It is not sensitive, though repeating it only bloats the transcript.

## If a secret leaks anyway — tell Charles immediately

If a decrypted value shows up in a tool result, the chat, a file this session reads back, or a git commit
(local, staged or pushed), **say so in the same session, the moment you notice** — which secret, where it
ended up, what you did about the local mess. Don't fix it quietly or downplay it once the file is deleted
or the commit amended. A plaintext credential that has touched a log, transcript or repo must be treated as
**compromised**; his protection is rotating it, and he can only do that once he knows. (`gitsync.sh` pushes
every 5 minutes, so a token written under `/config` is on GitHub quickly — and this repo is public.)

## Afterwards

Nothing required: the keyring lives under `/tmp` and the container is reclaimed at session end. To drop a
key deliberately, run `.claude/skills/fetching-secrets/scripts/cleanup.sh`. If you wrote a plaintext file
anywhere — you should not have — `shred -u` it in the same session.

## If a tool refuses

| It says | What it means |
|---|---|
| `not seeded on this box` | The server declares it but nobody has put a value there. Tell Charles. |
| `not on the allow-list` | The GitHub login attached to the request is not permitted. Charles's to change. |
| `no authenticated identity` | The request did not come through the server's auth proxy. |
| `switched off at the kill switch` | Deliberate. Ask before undoing it. |

If a `get_*` tool is missing from the session's tool list or the call is refused, **stop and tell Charles**
(the connector needs reconnecting, or the secret needs adding). Never fetch the value by another route.
