

git config core.sshCommand 'ssh -o UserKnownHostsFile=/config/.ssh/known_hosts -o StrictHostKeyChecking=no -i /config/.ssh/id_ed25519 -F /dev/null'

echo Starting git backup...
cd /config
git add .
git commit -am "Automated backup"

# Deliberately NO `git pull` here — do not add one back.
#
# Pulling remote changes is the Git pull add-on's job. It watches the remote and, when it
# pulls new commits, restarts Home Assistant if the config changed in a way that needs it.
# If this script pulls first, the add-on finds nothing new to pull, concludes the config is
# unchanged, and skips that restart — so merged changes land on disk but are never applied.
#
# Consequence: the push below is rejected while the remote is ahead (e.g. just after a PR
# merge). That is expected and self-correcting — the add-on pulls, and the next run five
# minutes later pushes cleanly.
git push
echo Git sync completed
