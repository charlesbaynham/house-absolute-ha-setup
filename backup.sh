{
  cd /config
  cp secret_files/id_rsa ~/.ssh/.

  git add .
  git commit -am "Automatic commit"
  git push
} 2>&1 | tee -a /config/backup_out.log
