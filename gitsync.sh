echo Starting git backup...
git add .
git commit -am "Automated backup"
git pull
git push
echo Git sync completed
