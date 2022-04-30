{
  set -o xtrace
  
  cd /config

  # Copy ssh key into this instance
  mkdir -p ~/.ssh
  cp secret_files/id_rsa ~/.ssh/.
  cp secret_files/id_rsa.pub ~/.ssh/.
  
  # Add the public key of the gitlab server
  # This can be (re)obtained with "ssh-keyscan -H gitlab.com > secret_files/known_hosts"
  cp secret_files/known_hosts ~/.ssh/known_hosts

  cat ~/.ssh/id_rsa.pub
  ls ~/.ssh

  git add .
  git commit -am "Automatic commit"
  GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa" git push -vv
} 2>&1 | tee -a /config/backup_out.log
