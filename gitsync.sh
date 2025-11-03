

git config core.sshCommand 'ssh -o UserKnownHostsFile=/config/.ssh/known_hosts -o StrictHostKeyChecking=no -i /config/.ssh/id_ed25519 -F /dev/null'

echo Starting git backup...
cd /config
git add .
git commit -am "Automated backup"
git pull
git push
echo Git sync completed
