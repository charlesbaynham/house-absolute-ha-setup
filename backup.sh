{
  cd /config
  cp secret_files/id_rsa ~/.ssh/.
  cp secret_files/id_rsa.pub ~/.ssh/.
  cat ~/.ssh/id_rsa.pub
  ls ~/.ssh

  git add .
  git commit -am "Automatic commit"
  GIT_SSH_COMMAND="ssh -i secret_files/id_rsa" git push
} 2>&1 | tee -a /config/backup_out.log
